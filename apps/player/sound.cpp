#include "sound.hpp"
#include <numbers>
namespace dc {
Sound::Sound() {
    SDL_AudioSpec spec{SDL_AUDIO_F32, 2, 48000};
    music = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, nullptr, nullptr);
    if (!music)
        return;
    effects = SDL_CreateAudioStream(&spec, &spec);
    if (effects)
        SDL_BindAudioStream(SDL_GetAudioStreamDevice(music), effects);
    SDL_ResumeAudioStreamDevice(music);
}
Sound::~Sound() {
    SDL_DestroyAudioStream(effects);
    SDL_DestroyAudioStream(music);
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
            played = std::clamp(played, std::max(origin, audio - .045), std::max(origin, audio + .025));
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
} // namespace dc
