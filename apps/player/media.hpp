#pragma once
#include "game.hpp"
#include <memory>
extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libswresample/swresample.h>
}
namespace dc {
struct PacketFree {
    void operator()(AVPacket *p) const { av_packet_free(&p); }
};
struct CodecFree {
    void operator()(AVCodecContext *p) const { avcodec_free_context(&p); }
};
struct FrameFree {
    void operator()(AVFrame *p) const { av_frame_free(&p); }
};
using Codec = std::unique_ptr<AVCodecContext, CodecFree>;
using Picture = std::unique_ptr<AVFrame, FrameFree>;
using Packet = std::unique_ptr<AVPacket, PacketFree>;
class Movie {
    std::vector<Packet> packets;
    Codec video;
    Picture picture{av_frame_alloc()};
    int current = -1;
    size_t compressedBytes = 0;
    AVPixelFormat expectedFormat;

  public:
    std::vector<float> audio;
    Movie(const fs::path &file, int count, int width = 1280, int height = 720,
          AVPixelFormat expectedFormat = AV_PIX_FMT_YUV420P);
    const AVFrame *at(int frame);
    size_t payloadBytes() const { return compressedBytes + audio.capacity() * sizeof(float); }
};
} // namespace dc
