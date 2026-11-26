#pragma once
#include "game.hpp"
#include "campaign_world.hpp"
#include "sound.hpp"
#include "tvgun.hpp"
#include <SDL3/SDL.h>
#include <optional>
namespace dc { struct Ink; }

namespace ca {
using namespace dc;
void drawGunBorder(Ink &ink);

struct DialogueCue {
    int begin, end;
    std::string voice, subtitle;
};
struct Film {
    std::string take, subtitle;
    int frames;
    std::string voice;
    bool autoSkip = false;
    std::vector<DialogueCue> cues;
    bool wallClockLimited = false;
    std::optional<bool> afterCivilian;
    int startFrame = 0, endFrame = -1;
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
    double playbackRate = 1., recallScale = 1.;
    bool linyuan = false, newFeedback = false, reducedFlash = false, protectAssist = false, shakeEnabled = true;
    bool directStoryWeak = false;
    std::string material = "feather";
    int tier = 2;
    double firstOpen = -1, closed = -1, inputTime = -1, firstFeedback = -1;
    Point inputPoint{};
    std::optional<Point> recordedPoint;
    int earlyTriggers = 0, lateTriggers = 0, replayOffset = 3;
    bool boundaryProbes = false, pauseProbe = false;
};

enum class FilmEnd { finished, skipped, quit, selected, expired };
struct TravelReload {
    int *arrows = nullptr;
    double *remaining = nullptr;
    double duration = .6;
    int *completed = nullptr;
    double *pausedSeconds = nullptr;
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
    double pausedSeconds = 0;
    bool subtitles = true;
    bool lastStoryCivilian = false;
    int musicVolume = 60, effectsVolume = 80, voiceVolume = 100;
    std::map<std::string, ChapterScore> scores;
    static Progress load(const fs::path &file);
    void save(const fs::path &file) const;
};

struct Stage {
    std::string id, chapter, heading, level, music;
    std::vector<Film> films;
    Json trial;
    int cardMillis = 0;
    std::string cardText;
    bool linyuan = false;
    bool allowSpecial = false;
};

struct Campaign {
    std::string title;
    fs::path titleArt;
    std::vector<Stage> stages;
    bool linyuan;
    Campaign(const CampaignWorld &world, const std::string &name);
    size_t locate(const std::string &stage) const;
};

FilmEnd playTrial(SDL_Window *window, SDL_Renderer *renderer, const CampaignWorld &world, const Stage &stage,
                  Progress &state, Receiver *gun, bool automated, const fs::path &evidence,
                  const std::string &scenario, ScoreAudio *score, int &completedReloads,
                  bool newFeedback = false, bool reducedFlash = false, const fs::path &inputSource = {},
                  bool shakeEnabled = true);

enum class MenuChoice { resume, newGame, quit };
bool chapterResults(SDL_Renderer *renderer, const Stage &stage, const ChapterScore &score,
                    Receiver *receiver, bool automated, ScoreAudio *music, bool linyuan = false);
MenuChoice campaignMenu(SDL_Renderer *renderer, const Campaign &campaign, Progress &state,
                        Receiver *receiver, bool automated, ScoreAudio *music = nullptr);
} // namespace ca
