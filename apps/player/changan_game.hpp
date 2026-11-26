#pragma once
#include "game.hpp"
#include <optional>

namespace ca {
using namespace dc;

enum class Kind { none, target, projectile, civilian };
enum class Cue { none, hit, purify, intercept, miss, hurt, reload, ready, empty, special, civilian };

struct Difficulty {
    std::string id, label;
    int lives, charge, eliteBonus, aimRadius, civilianDamage;
    double reloadSeconds, warningScale, projectileScale;
};
const Difficulty &difficulty(const std::string &id);

struct Window {
    int begin, end, node;
    Kind kind;
    std::string onHit;
    bool weak = false;
};

struct VoiceCue {
    int frame;
    std::string voice, subtitle;
    int priority;
};

struct WeakSpot {
    Point center;
    double height;
};

struct Scene {
    Clip image;
    Clip weakArea;
    std::vector<std::vector<WeakSpot>> weakSpots;
    std::vector<Window> windows;
    std::vector<VoiceCue> voiceCues;
    std::map<int, std::array<double, 9>> materialTransforms;
    std::array<std::map<int, Point>, 2> threatTracks;
    std::string inAnchor, outAnchor, mediaId, attack;
    int launch = -1, impact = -1, warning = -1, end = 0;
    double holdSeconds = 0;
    double speed = 1;
    bool allowEarlyMiss = false;
    std::string minimumDifficulty = "easy";

    const Window *window(int frame) const;
    Point center(int frame) const;
    bool weakAt(int frame, Point position) const;
    bool aimCovers(int frame, Point position, int radius) const;
};

struct Node {
    std::string id, label, flinch;
    int hp, score;
    int weakBonus = 0, kills = 1;
    bool fixedScore = false;
    int weakDamage = 1;
    std::string material;
    int tier = 0;
};

struct MovieEntry {
    std::string source, destination, file, hash;
    int begin, end;
};

struct Street {
    int frames;
    std::string hash;
};

struct Encounter {
    std::map<std::string, Scene> scenes;
    std::vector<Node> nodes;
    std::vector<MovieEntry> entries;
    std::optional<Street> street;
    std::string title, first, location, briefing, cleared;
    int width, height;
    bool selectableDifficulty = false;
    bool linyuan = false;
    std::vector<std::vector<std::string>> materials;
    std::string materialAt(Point point) const;
    std::string materialAt(const Scene &scene, int frame, Point point) const;
    explicit Encounter(const fs::path &dir);
    const MovieEntry *entrance(const Scene &from, const std::string &to, int frame) const;
};

struct Match {
    const Encounter &encounter;
    Difficulty rules;
    const Scene *scene = nullptr;
    Screen screen = Screen::title;
    int progress = 0, hp = 0, lives = 3, arrows = 8, hits = 0, shots = 0, score = 0, combo = 0, bestCombo = 0,
        energy = 0, generation = 0, launches = 0, hurts = 0, blocks = 0, reloads = 0, civilianHits = 0;
    int kills = 0, weakReturns = 0;
    bool attacked = false, launched = false, paused = false, interceptRewarded = false, lastWeakHit = false;
    std::string pending;
    double frozenUntil = 0, reloadLeft = 0, reloadStartedAt = 0, elapsed = 0, targetOpened = -1;
    double hurtFreezeLeft = 0;
    bool hurtFreezeStarted = false;
    explicit Match(const Encounter &e);
    int health(const Node &node) const;
    double playbackRate(int frame) const;
    void enter(const std::string &id);
    void start(int initialEnergy = 0);
    void title();
    Cue input(Point position, int gen, int frame, bool thunder, double now);
    Cue present(int gen, int frame);
    Cue tick(double dt, double now);
    Cue reload(double now);
    bool isFrozen() const { return hurtFreezeLeft > 0; }
    bool interactive() const { return screen == Screen::play && !paused && !isFrozen() && pending.empty(); }
    bool active(const Window *w) const { return w && w->node == progress; }
};
} // namespace ca
