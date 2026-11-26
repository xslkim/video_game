#pragma once
#include "media.hpp"
#include <SDL3/SDL.h>
namespace dc {
class Sound {
    SDL_AudioDeviceID playback = 0;
    SDL_AudioStream *music = nullptr;
    SDL_AudioStream *effects = nullptr;
    double epoch = 0, origin = 0, rate = 1, held = 0;
    int count = 0;
    bool stopped = false;
    bool wallClockLimit = false;
    std::vector<float> captured;
    size_t capturedSize = 0;
    int captureRate = 0, captureChannels = 0;
    uint64_t captureStart = 0;
    bool captureError = false;
    static void SDLCALL postmix(void *user, const SDL_AudioSpec *spec, float *buffer, int bytes);

  public:
    Sound();
    ~Sound();
    bool available() const { return music != nullptr; }
    SDL_AudioDeviceID device() const { return playback; }
    void begin(const Movie &movie, int frame, double speed, double now);
    void pause(bool yes, double now);
    void silenceClip();
    void clipGain(float gain) { if (music) SDL_SetAudioStreamGain(music,gain); }
    int localFrame(double now) const;
    void limitToWallClock(bool enabled) { wallClockLimit = enabled; }
    void cue(Feedback event);
    void startCapture(int maxSeconds = 185);
    void finishCapture(const fs::path &directory, double begun);
};

// The campaign score and performance effects continue across action-video cuts.
class ScoreAudio {
    using Stream = std::unique_ptr<SDL_AudioStream, decltype(&SDL_DestroyAudioStream)>;
    std::map<std::string, std::vector<Uint8>> samples;
    std::map<std::string, unsigned> cueVisits;
    std::vector<Stream> voices;
    Stream backing{nullptr, SDL_DestroyAudioStream};
    std::vector<Uint8> track;
    fs::path currentTrack;
    size_t position = 0, nextVoice = 0;
    float musicLevel = 1.f, effectsLevel = 1.f, backingScale = 1.f;
    bool playing = false;

  public:
    void open(SDL_AudioDeviceID device, const fs::path &folder, bool withMusic = true,
              const std::string &initialTrack = "festival");
    void openLoop(SDL_AudioDeviceID device, const fs::path &file);
    bool cue(const std::string &name, float pitch = 1.f, float gain = 1.f, int recalledSwords = 8);
    void update(bool active);
    void rewind();
    void volume(float musicGain, float effectsGain);
    void scaleMusic(float scale);
    void selectTrack(const fs::path &file);
};
} // namespace dc
