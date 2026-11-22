#pragma once
#include "media.hpp"
#include <SDL3/SDL.h>
namespace dc {
class Sound {
    SDL_AudioStream *music = nullptr;
    SDL_AudioStream *effects = nullptr;
    double epoch = 0, origin = 0, rate = 1, held = 0;
    int count = 0;
    bool stopped = false;

  public:
    Sound();
    ~Sound();
    bool available() const { return music != nullptr; }
    void begin(const Movie &movie, int frame, double speed, double now);
    void pause(bool yes, double now);
    int localFrame(double now) const;
    void cue(Feedback event);
};
} // namespace dc
