#include "sound.hpp"
#include <numbers>
namespace dc {
Sound::Sound() {
    SDL_AudioSpec spec{SDL_AUDIO_F32, 2, 48000};
    playback = SDL_OpenAudioDevice(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec);
    if (!playback)
        return;
    music = SDL_CreateAudioStream(&spec, &spec);
    if (!music || !SDL_BindAudioStream(playback, music)) {
        SDL_DestroyAudioStream(music);
        music = nullptr;
        SDL_CloseAudioDevice(playback);
        playback = 0;
        return;
    }
    effects = SDL_CreateAudioStream(&spec, &spec);
    if (effects)
        SDL_BindAudioStream(SDL_GetAudioStreamDevice(music), effects);
    SDL_ResumeAudioDevice(playback);
}
Sound::~Sound() {
    if (!captured.empty() && playback)
        SDL_SetAudioPostmixCallback(playback,nullptr,nullptr);
    SDL_DestroyAudioStream(effects);
    SDL_DestroyAudioStream(music);
    if (playback)
        SDL_CloseAudioDevice(playback);
}
void SDLCALL Sound::postmix(void *user, const SDL_AudioSpec *spec, float *buffer, int bytes) {
    auto &s = *static_cast<Sound *>(user);
    if (!s.captureStart) s.captureStart = SDL_GetTicksNS();
    const size_t count = size_t(bytes) / sizeof(float);
    if ((s.captureRate && (s.captureRate != spec->freq || s.captureChannels != spec->channels)) ||
        count > s.captured.size() - s.capturedSize) {
        s.captureError = true;
        return;
    }
    s.captureRate = spec->freq;
    s.captureChannels = spec->channels;
    std::copy_n(buffer,count,s.captured.data()+s.capturedSize);
    s.capturedSize += count;
}

void Sound::startCapture(int maxSeconds) {
    SDL_AudioSpec format{};
    if (!playback || !SDL_GetAudioDeviceFormat(playback,&format,nullptr))
        throw std::runtime_error("No audio device for replay capture");
    capturedSize = captureStart = 0;
    captureRate = captureChannels = 0;
    captureError = false;
    captured.resize(size_t(format.freq) * format.channels * maxSeconds);
    if (!SDL_SetAudioPostmixCallback(playback,postmix,this))
        throw std::runtime_error(SDL_GetError());
}

void Sound::finishCapture(const fs::path &directory, double begun) {
    if (captured.empty()) return;
    SDL_SetAudioPostmixCallback(playback,nullptr,nullptr);
    if (captureError || capturedSize == 0)
        throw std::runtime_error("Incomplete audio capture");
    std::ofstream raw(directory / "postmix.f32",std::ios::binary);
    raw.exceptions(std::ios::failbit | std::ios::badbit);
    raw.write(reinterpret_cast<const char *>(captured.data()),capturedSize * sizeof(float));
    Json format{{"sample_rate",captureRate},{"channels",captureChannels},{"samples",capturedSize/captureChannels},
                {"start_time",captureStart / 1e9 - begun}};
    std::ofstream(directory / "postmix.json") << format.dump(2) << '\n';
    captured.clear();
}
void Sound::silenceClip() {
    if (music)
        SDL_ClearAudioStream(music);
}
void Sound::begin(const Movie &movie, int frame, double speed, double now) {
    origin = frame / 24.;
    epoch = now;
    held = origin;
    rate = speed;
    stopped = false;
    count = int(movie.audio.size() / 2);
    if (music) {
        SDL_ClearAudioStream(music);
        SDL_SetAudioStreamFrequencyRatio(music, float(rate));
        int offset = std::min(count, frame * 2000) * 2;
        SDL_PutAudioStreamData(music, movie.audio.data() + offset,
                               int(movie.audio.size() - offset) * sizeof(float));
        SDL_FlushAudioStream(music);
        SDL_ResumeAudioStreamDevice(music);
    }
}
void Sound::pause(bool yes, double now) {
    if (stopped == yes)
        return;
    if (yes) {
        held = origin + (now - epoch) * rate;
        if (music)
            SDL_PauseAudioStreamDevice(music);
    } else {
        epoch = now;
        origin = held;
        if (music)
            SDL_ResumeAudioStreamDevice(music);
    }
    stopped = yes;
}
int Sound::localFrame(double now) const {
    double played = stopped ? held : origin + (now - epoch) * rate;
    if (music && !stopped) {
        // The device pulls blocks ahead. Interpolate within the device block and
        // avoid driving video forward while the audio stream is stalled.
        int queued = SDL_GetAudioStreamQueued(music);
        if (queued >= 0 && queued > 0) {
            double audio = (count - queued / int(2 * sizeof(float))) / 48000.;
            const double latest = std::max(origin, audio + .025);
            // A device may pull a large block ahead of playback, especially under capture.
            // An authored time window must never run faster than its monotonic clock.
            played = wallClockLimit ? std::min(played, latest)
                                    : std::clamp(played, std::max(origin, audio - .045), latest);
        }
    }
    return int(std::floor(24 * played + 1e-7));
}
void Sound::cue(Feedback e) {
    if (!effects || e == Feedback::none)
        return;
    double duration = (e == Feedback::hurt || e == Feedback::civilian) ? .18 : .085;
    std::vector<float> pcm(int(48000 * duration) * 2);
    uint32_t noise = 7931;
    for (int i = 0; i < int(pcm.size() / 2); ++i) {
        double t = i / 48000.;
        noise = 1664525u * noise + 1013904223u;
        double n = (noise / double(UINT32_MAX) - .5);
        double v = 0;
        switch (e) {
        case Feedback::hurt:
        case Feedback::civilian:
            v = .43 * n + .24 * sin(2 * std::numbers::pi * 95 * t);
            break;
        case Feedback::miss:
        case Feedback::hit:
        case Feedback::rescue:
            v = .42 * n + .25 * sin(2 * std::numbers::pi * 125 * t);
            break;
        case Feedback::bonus:
            v = .22 * sin(2 * std::numbers::pi * 780 * t);
            break;
        default:
            v = .17 * n + .14 * sin(2 * std::numbers::pi * 420 * t);
            break;
        }
        pcm[i * 2] = pcm[i * 2 + 1] = float(v * std::exp(-5 * t / duration));
    }
    SDL_PutAudioStreamData(effects, pcm.data(), int(pcm.size() * sizeof(float)));
}
static std::vector<Uint8> readMusicPcm(const fs::path &file) {
    const SDL_AudioSpec format{SDL_AUDIO_S16,2,48000};
        SDL_AudioSpec src{};
        Uint8 *raw = nullptr;
        Uint32 length = 0;
        const auto path = file.u8string();
        if (!SDL_LoadWAV(reinterpret_cast<const char *>(path.c_str()),&src,&raw,&length))
            throw std::runtime_error("Cannot read audio cue: " + file.filename().string());
        std::unique_ptr<Uint8,decltype(&SDL_free)> owner(raw,SDL_free);
        if (src.format != format.format || src.channels != format.channels || src.freq != format.freq || !length)
            throw std::runtime_error("Invalid campaign PCM format: " + file.filename().string());
    return std::vector<Uint8>(raw,raw+length);
}

void ScoreAudio::open(SDL_AudioDeviceID device, const fs::path &folder, bool withMusic,
                      const std::string &initialTrack) {
    if (!device || !fs::exists(folder))
        return;
    const SDL_AudioSpec format{SDL_AUDIO_S16,2,48000};
    auto stream = [&]() {
        Stream output(SDL_CreateAudioStream(&format,&format),SDL_DestroyAudioStream);
        if (!output || !SDL_BindAudioStream(device,output.get()))
            throw std::runtime_error(SDL_GetError());
        return output;
    };
    if (fs::is_directory(folder / "foley")) {
        for (const auto &entry : fs::directory_iterator(folder / "foley"))
            if (entry.path().extension() == ".wav")
                samples.emplace(entry.path().stem().string(), readMusicPcm(entry.path()));
    }
    for (int i = 0; i < 6; ++i)
        voices.push_back(stream());
    if (withMusic) {
        backing = stream();
        if (!initialTrack.empty())
            selectTrack(folder / "music" / (initialTrack + ".wav"));
    }
    volume(.64f,.80f);
}

void ScoreAudio::selectTrack(const fs::path &file) {
    if (!backing || currentTrack == file) return;
    auto next = readMusicPcm(file);
    SDL_ClearAudioStream(backing.get());
    position = 0;
    playing = false;
    currentTrack = file;
    track = std::move(next);
}

void ScoreAudio::openLoop(SDL_AudioDeviceID device, const fs::path &file) {
    if (!device)
        return;
    const SDL_AudioSpec format{SDL_AUDIO_S16, 2, 48000};
    backing.reset(SDL_CreateAudioStream(&format, &format));
    if (!backing || !SDL_BindAudioStream(device, backing.get()))
        throw std::runtime_error(SDL_GetError());
    selectTrack(file);
}

bool ScoreAudio::cue(const std::string &name, float pitch, float gain, int recalledSwords) {
    const unsigned variant=cueVisits[name]++%3;
    auto it=variant ? samples.find(name+"_"+std::to_string(variant+1)) : samples.end();
    if (it==samples.end()) it=samples.find(name);
    if (it == samples.end())
        return false;
    auto *out = voices[nextVoice++ % voices.size()].get();
    SDL_ClearAudioStream(out);
    SDL_SetAudioStreamGain(out, effectsLevel * gain);
    SDL_SetAudioStreamFrequencyRatio(out, pitch);
    const auto &pcm = it->second;
    // Linyuan's recall master contains a 160ms pickup followed by eight 55ms sheath strokes.
    constexpr size_t pickup = 7680 * 4, stroke = 2640 * 4;
    if (name == "reload" && recalledSwords >= 1 && recalledSwords < 8 && pcm.size() == pickup + 8 * stroke) {
        const size_t tail = size_t(recalledSwords) * stroke;
        SDL_PutAudioStreamData(out, pcm.data(), int(pickup));
        SDL_PutAudioStreamData(out, pcm.data()+pcm.size()-tail, int(tail));
    } else {
        SDL_PutAudioStreamData(out, pcm.data(), int(pcm.size()));
    }
    SDL_FlushAudioStream(out);
    return true;
}

void ScoreAudio::volume(float musicGain, float effectsGain) {
    musicLevel = musicGain;
    effectsLevel = effectsGain;
    if (backing) SDL_SetAudioStreamGain(backing.get(),musicLevel * backingScale);
    for (auto &voice : voices)
        SDL_SetAudioStreamGain(voice.get(),effectsGain);
}

void ScoreAudio::scaleMusic(float scale) {
    if (scale == backingScale) return;
    backingScale = scale;
    if (backing) SDL_SetAudioStreamGain(backing.get(), musicLevel * backingScale);
}

void ScoreAudio::rewind() {
    position = 0;
    playing = false;
    if (backing) SDL_ClearAudioStream(backing.get());
    for (auto &voice : voices) SDL_ClearAudioStream(voice.get());
}

void ScoreAudio::update(bool active) {
    if (!backing || track.empty())
        return;
    if (!active && playing) {
        int queued = std::max(0, SDL_GetAudioStreamQueued(backing.get()));
        position = (position + track.size() - size_t(queued) % track.size()) % track.size();
        SDL_ClearAudioStream(backing.get());
    }
    playing = active;
    if (active && SDL_GetAudioStreamQueued(backing.get()) < 24000) {
        const auto count = std::min<size_t>(48000, track.size()-position);
        SDL_PutAudioStreamData(backing.get(),track.data()+position,int(count));
        position = (position+count) % track.size();
    }
}
} // namespace dc
