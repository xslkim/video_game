#include "game.hpp"
#include <iomanip>
#include <sstream>
namespace dc {
static Point point(const Json &p) { return {p.at(0), p.at(1)}; }
static uint16_t read16(std::istream &in) {
    uint8_t b[2];
    if (!in.read(reinterpret_cast<char *>(b), 2))
        throw std::runtime_error("Incomplete mask");
    return uint16_t(b[0] + 256 * b[1]);
}
Level::Level(const fs::path &dir) {
    std::ifstream file(dir / "level.json");
    auto data = Json::parse(file);
    if (data.at("version") != 1 || data.at("fps") != 24)
        throw std::runtime_error("Unsupported level");
    checkpoints = data.at("checkpoints");
    subtitle = data.at("subtitle");
    rescue = point(data.at("rescue"));
    protect = point(data.at("protect"));
    for (auto &[id, j] : data.at("clips").items()) {
        auto &c = clips[id];
        c.id = id;
        c.next = j.at("next");
        c.hash = j.at("sha256");
        c.frames = j.at("frames");
        c.success = j.value("success", "");
        c.beat = j.value("beat", "");
        c.opens = j.value("opens", 0);
        c.start = j.value("start", 0);
        c.expires = j.value("expires", -1);
        c.civilian = j.value("civilian", false);
        if (j.contains("point"))
            c.point = point(j.at("point"));
        if ((!c.beat.empty() && c.beat != "porch") || c.civilian) {
            std::ifstream in(dir / (id + ".mask"), std::ios::binary);
            char magic[4];
            uint8_t hash[32];
            if (!in.read(magic, 4) || std::string(magic, 4) != "DCM1" ||
                !in.read(reinterpret_cast<char *>(hash), 32))
                throw std::runtime_error("Missing mask: " + id);
            std::ostringstream hex;
            for (auto b : hash)
                hex << std::hex << std::setw(2) << std::setfill('0') << int(b);
            if (hex.str() != c.hash || read16(in) != c.frames)
                throw std::runtime_error("Outdated mask: " + id);
            c.masks.resize(c.frames);
            for (auto &m : c.masks) {
                int n = read16(in);
                m.reserve(n);
                for (int i = 0; i < n; ++i) {
                    auto y = read16(in), x = read16(in), end = read16(in);
                    if (y >= 360 || end > 640 || x >= end)
                        throw std::runtime_error("Invalid span: " + id);
                    m.push_back({y, x, end});
                }
            }
        }
    }
}
void Game::enter(const std::string &id) {
    ++generation;
    if (id == "@complete" || id == "@failed") {
        screen = id == "@complete" ? Screen::complete : Screen::failed;
        frame = clip->frames - 1;
        return;
    }
    clip = &level.clips.at(id);
    frame = clip->start;
    expired = false;
    civilPenalty = false;
    shotInCross = false;
    if (id != "D01_badge")
        checkpoint = id.substr(0, 2);
}
void Game::start(bool resume) {
    auto entry = resume ? level.checkpoints.at(checkpoint) : level.checkpoints.at("A0");
    lives = 3;
    ammo = 6;
    score = combo = hits = shots = injuries = responseFrames = 0;
    mercy = false;
    reloadTime = feedbackTime = 0;
    feedback = Feedback::none;
    paused = false;
    screen = Screen::play;
    enter(entry);
}
void Game::skip() {
    if (interactive() && clip->id.starts_with("A0_mayor"))
        enter("A0_travel_main");
}
void Game::tick(double dt) {
    if (!interactive())
        return;
    feedbackTime = std::max(0., feedbackTime - dt);
    if (reloadTime > 0) {
        reloadTime = std::max(0., reloadTime - dt);
        if (reloadTime == 0)
            ammo = 6;
    }
}
void Game::hurt(bool tutorial) {
    ++injuries;
    combo = 0;
    lives = std::max(tutorial ? 1 : 0, lives - 1);
    signal(Feedback::hurt, .65);
    if (!lives) {
        mercy = false;
        reloadTime = 0;
        enter("D01_badge");
    }
}
void Game::present(int f) {
    if (!interactive())
        return;
    frame = std::min(f, clip->frames - 1);
    if (clip->expires >= 0 && frame >= clip->expires && !expired) {
        expired = true;
        hurt(clip->beat == "wagon");
        if (!lives)
            return;
    }
    if (f < clip->frames)
        return;
    if (clip->civilian && !shotInCross) {
        score += 500;
        signal(Feedback::bonus);
    }
    mercy = clip->expires >= 0 && expired;
    enter(clip->next);
}
void Game::reload() {
    if (!interactive() || clip->id == "D01_badge" || clip->id == "A4_change_doors" || ammo >= 6 ||
        reloadTime > 0)
        return;
    reloadTime = .5;
    signal(Feedback::reload, .5);
}
static bool near(Point p, Point q, double r) { return std::hypot(p.x - q.x, p.y - q.y) <= r; }
void Game::shoot(Point p, int gen, int f) {
    if (!interactive() || gen != generation || reloadTime > 0 || (!clip->civilian && !enabled(f)))
        return;
    if (!ammo) {
        signal(Feedback::empty);
        return;
    }
    --ammo;
    ++shots;
    if (clip->civilian) {
        shotInCross = true;
        combo = 0;
        if (!civilPenalty && clip->covers(f, p)) {
            civilPenalty = true;
            hurt(false);
            if (lives)
                signal(Feedback::civilian);
        } else
            signal(Feedback::miss);
        return;
    }
    const bool rescue = clip->beat == "porch";
    if (rescue && near(p, level.protect, 30)) {
        hurt(false);
        if (lives) {
            signal(Feedback::civilian);
            mercy = false;
            enter("A4_scare");
        }
        return;
    }
    if (!(rescue ? near(p, level.rescue, 30) : clip->covers(f, p))) {
        combo = 0;
        signal(Feedback::miss);
        return;
    }
    const int elapsed = clip->expires < 0 ? 0 : std::max(0, f - clip->start);
    const double fraction = elapsed / double(std::max(1, clip->expires - clip->start));
    score += int(std::lround(1000 * (1 - .7 * fraction) * (1 + std::min(combo, 10) * .1)));
    ++combo;
    ++hits;
    responseFrames += int(std::lround(elapsed / speed()));
    mercy = false;
    signal(rescue ? Feedback::rescue : Feedback::hit);
    enter(clip->success);
}
} // namespace dc
