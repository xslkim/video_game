#include "media.hpp"
#include <sstream>
namespace dc {
static void check(int code, const char *what) {
    if (code < 0) {
        char msg[AV_ERROR_MAX_STRING_SIZE];
        av_strerror(code, msg, sizeof(msg));
        throw std::runtime_error(std::string(what) + ": " + msg);
    }
}
static Codec decoder(AVStream *stream) {
    const auto *dec = avcodec_find_decoder(stream->codecpar->codec_id);
    if (!dec)
        throw std::runtime_error("Decoder unavailable");
    Codec ctx(avcodec_alloc_context3(dec));
    if (!ctx)
        throw std::bad_alloc();
    check(avcodec_parameters_to_context(ctx.get(), stream->codecpar), "codec parameters");
    // FFV1 foregrounds are encoded in independent slices. Frame threading
    // adds latency and would break the one-packet/one-picture seek contract.
    ctx->thread_count = stream->codecpar->codec_id == AV_CODEC_ID_FFV1 ? 4 : 1;
    ctx->thread_type = FF_THREAD_SLICE;
    check(avcodec_open2(ctx.get(), dec, nullptr), "open decoder");
    return ctx;
}
Movie::Movie(const fs::path &path, int count, int width, int height, AVPixelFormat format)
    : expectedFormat(format) {
    auto u8 = path.u8string();
    AVFormatContext *raw = nullptr;
    check(avformat_open_input(&raw, reinterpret_cast<const char *>(u8.c_str()), nullptr, nullptr),
          "open movie");
    auto close = [](AVFormatContext *f) { avformat_close_input(&f); };
    std::unique_ptr<AVFormatContext, decltype(close)> file(raw, close);
    check(avformat_find_stream_info(raw, nullptr), "stream info");
    int v = av_find_best_stream(raw, AVMEDIA_TYPE_VIDEO, -1, -1, nullptr, 0);
    int a = av_find_best_stream(raw, AVMEDIA_TYPE_AUDIO, -1, -1, nullptr, 0);
    check(v, "video stream");
    check(a, "audio stream");
    video = decoder(raw->streams[v]);
    auto sound = decoder(raw->streams[a]);
    AVChannelLayout stereo = AV_CHANNEL_LAYOUT_STEREO;
    SwrContext *ptr = nullptr;
    check(swr_alloc_set_opts2(&ptr, &stereo, AV_SAMPLE_FMT_FLT, 48000, &sound->ch_layout,
                              sound->sample_fmt, sound->sample_rate, 0, nullptr),
          "audio setup");
    auto freeResampler = [](SwrContext *s) { swr_free(&s); };
    std::unique_ptr<SwrContext, decltype(freeResampler)> resampler(ptr, freeResampler);
    check(swr_init(ptr), "audio init");
    Picture decoded(av_frame_alloc());
    Packet pkt(av_packet_alloc());
    auto convert = [&](const uint8_t **data, int samples) {
        int room = std::max(256, swr_get_out_samples(ptr, samples));
        size_t offset = audio.size();
        audio.resize(offset + 2 * room);
        auto *dest = reinterpret_cast<uint8_t *>(audio.data() + offset);
        int n = swr_convert(ptr, &dest, room, data, samples);
        check(n, "resample");
        audio.resize(offset + 2 * n);
        return n;
    };
    auto drain = [&] {
        for (;;) {
            int result = avcodec_receive_frame(sound.get(), decoded.get());
            if (result == AVERROR(EAGAIN) || result == AVERROR_EOF)
                break;
            check(result, "decode sound");
            convert(const_cast<const uint8_t **>(decoded->extended_data), decoded->nb_samples);
            av_frame_unref(decoded.get());
        }
    };
    int status;
    while ((status = av_read_frame(raw, pkt.get())) >= 0) {
        if (pkt->stream_index == v) {
            compressedBytes += pkt->size;
            packets.emplace_back(av_packet_clone(pkt.get()));
            if (!packets.back())
                throw std::bad_alloc();
        }
        if (pkt->stream_index == a) {
            check(avcodec_send_packet(sound.get(), pkt.get()), "audio packet");
            drain();
        }
        av_packet_unref(pkt.get());
    }
    if (status != AVERROR_EOF)
        check(status, "demux");
    check(avcodec_send_packet(sound.get(), nullptr), "flush sound");
    drain();
    while (convert(nullptr, 0) > 0) {
    }
    if (int(packets.size()) != count || video->width != width || video->height != height ||
        video->has_b_frames)
        throw std::runtime_error("Unexpected movie layout: " + path.filename().string());
    audio.resize(size_t(count) * 2000 * 2);
    at(0);
}
const AVFrame *Movie::at(int f) {
    if (f < 0 || f >= int(packets.size()))
        throw std::out_of_range("Video frame");
    if (f < current || f > current + 20) {
        int begin = f;
        while (begin > 0 && !(packets[begin]->flags & AV_PKT_FLAG_KEY))
            --begin;
        avcodec_flush_buffers(video.get());
        current = begin - 1;
    }
    while (current < f) {
        check(avcodec_send_packet(video.get(), packets.at(current + 1).get()), "video packet");
        av_frame_unref(picture.get());
        check(avcodec_receive_frame(video.get(), picture.get()), "decode picture");
        ++current;
    }
    if (picture->format != expectedFormat &&
        !(expectedFormat == AV_PIX_FMT_YUV420P && picture->format == AV_PIX_FMT_YUVJ420P))
        throw std::runtime_error("Unexpected decoded movie pixel format");
    return picture.get();
}
} // namespace dc
