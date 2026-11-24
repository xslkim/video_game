#pragma once
#include "game.hpp"
#include "sound.hpp"
#include "tvgun.hpp"
#include <SDL3/SDL.h>
namespace dc { struct Ink; }

namespace ca {
using namespace dc;
void drawGunBorder(Ink &ink);

struct Film {
    std::string take, subtitle;
    int frames;
    std::string voice;
    bool autoSkip = false;
};

struct TrackedRegion {
    std::string id;
    std::map<int, std::vector<Point>> outlines;
    int begin = 0, end = 65535;
    std::vector<Point> outline(int frame) const;
    bool covers(int frame, Point p, double margin = 0) const;
};

struct FilmChoice {
    int begin, end;
    std::string prompt, answer;
    std::vector<TrackedRegion> regions;
    std::string selected;
    bool fired = false;
    bool story = true;
    int ammo = 8, lives = 3;
    double reloadDuration = .6;
    bool highlight = false, canExpose = false, exposed = false;
    bool canStrike = false, spent = false, specialFinish = false;
    bool autoSpecial = false;
    int specialDamage = 0;
    int wasted = 0;
    int strength = 1, partialHits = 0, reloads = 0;
    std::vector<std::string> guards;
    std::string replayAnswer;
    int assist = 0;
    int hitFrame = -1;
    std::vector<std::string> eligible;
};

enum class FilmEnd { finished, skipped, quit, selected, expired };
struct TravelReload {
    int *arrows = nullptr;
    double *remaining = nullptr;
    double duration = .6;
    int *completed = nullptr;
};
FilmEnd playFilm(SDL_Window *window, SDL_Renderer *renderer, const fs::path &media, const Film &film,
                 bool subtitles, Receiver *receiver, bool automated, FilmChoice *choice = nullptr,
                 ScoreAudio *score = nullptr, float voiceGain = 1.f, float effectsGain = .8f,
                 TravelReload travel = {});

struct ChapterScore {
    int points = 0, hits = 0, shots = 0, combo = 0, damage = 0, purified = 0;
    void add(const ChapterScore &section);
    std::string grade() const;
};

struct Progress {
    std::string next, difficulty = "normal";
    int lives = 3, energy = 0, arrows = 8;
    double reloadRemaining = 0;
    bool subtitles = true;
    int musicVolume = 60, effectsVolume = 80, voiceVolume = 100;
    std::map<std::string, ChapterScore> scores;
    static Progress load(const fs::path &file);
    void save(const fs::path &file) const;
};

struct Stage {
    std::string id, chapter, heading, level, music;
    std::vector<Film> films;
    Json trial;
};

struct Campaign {
    std::string title;
    fs::path titleArt;
    std::vector<Stage> stages;
    Campaign(const fs::path &root, const std::string &name);
    size_t locate(const std::string &stage) const;
};

FilmEnd playTrial(SDL_Window *window, SDL_Renderer *renderer, const fs::path &root, const Stage &stage,
                  Progress &state, Receiver *gun, bool automated, const fs::path &evidence,
                  const std::string &scenario, ScoreAudio *score, int &completedReloads);

enum class MenuChoice { resume, newGame, quit };
bool chapterResults(SDL_Renderer *renderer, const Stage &stage, const ChapterScore &score,
                    Receiver *receiver, bool automated, ScoreAudio *music);
MenuChoice campaignMenu(SDL_Renderer *renderer, const Campaign &campaign, Progress &state,
                        Receiver *receiver, bool automated, ScoreAudio *music = nullptr);
} // namespace ca
