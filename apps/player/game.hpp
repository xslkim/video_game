#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>

namespace dc {
namespace fs = std::filesystem;
using Json = nlohmann::json;
struct Point {
    double x{}, y{};
};
struct Span {
    uint16_t y, x0, x1;
};
struct Clip {
    std::string id, next, success, beat, hash;
    int frames{}, opens{}, expires{-1}, start{};
    bool civilian{};
    Point point{};
    std::vector<std::vector<Span>> masks;
    bool covers(int frame, Point p) const {
        if (frame < 0 || frame >= int(masks.size()) || p.x < 0 || p.y < 0)
            return false;
        const auto &row = masks[frame];
        const int y = int(p.y) / 2, x = int(p.x) / 2;
        auto it = std::lower_bound(row.begin(), row.end(), y, [](Span s, int v) { return s.y < v; });
        for (; it != row.end() && it->y == y; ++it)
            if (it->x0 <= x && x < it->x1)
                return true;
        return false;
    }
};
struct Level {
    std::map<std::string, Clip> clips;
    std::map<std::string, std::string> checkpoints;
    std::string subtitle;
    Point rescue, protect;
    explicit Level(const fs::path &dir);
};
enum class Screen { title, play, complete, failed };
enum class Feedback { none, hit, miss, hurt, civilian, rescue, bonus, empty, reload };
struct Game {
    const Level &level;
    Screen screen = Screen::title;
    const Clip *clip = nullptr;
    int frame = 0, generation = 0, lives = 3, ammo = 6, score = 0, combo = 0, hits = 0, shots = 0,
        injuries = 0;
    int responseFrames = 0;
    double reloadTime = 0, feedbackTime = 0;
    Feedback feedback = Feedback::none;
    bool paused = false, expired = false, civilPenalty = false, shotInCross = false, mercy = false;
    std::string checkpoint = "A0";
    explicit Game(const Level &l) : level(l) {}
    void enter(const std::string &id);
    void start(bool resume = false);
    void skip();
    void tick(double seconds);
    void present(int localFrame);
    void shoot(Point p, int displayedGeneration, int displayedFrame);
    void reload();
    void signal(Feedback f, double seconds = .45) {
        feedback = f;
        feedbackTime = seconds;
    }
    void hurt(bool tutorial);
    bool interactive() const { return screen == Screen::play && !paused; }
    bool enabled(int f) const {
        return clip && !clip->beat.empty() && !expired && f >= clip->opens &&
               (clip->expires < 0 || f < clip->expires);
    }
    double speed() const { return mercy && clip && clip->expires >= 0 ? .8 : 1.; }
};
} // namespace dc
