#include "changan_game.hpp"
#include <iomanip>
#include <set>
#include <sstream>

namespace ca {
namespace {
bool coversWithAssist(const Clip &clip, int frame, Point p, int radius) {
    if (clip.covers(frame, p))
        return true;
    if (!radius || frame < 0 || frame >= int(clip.masks.size()))
        return false;
    const auto &spans = clip.masks[frame];
    for (const auto &span : spans) {
        double dy = p.y - std::clamp(p.y, 2. * span.y, 2. * span.y + 1.);
        double dx = p.x - std::clamp(p.x, 2. * span.x0, 2. * span.x1 - 1.);
        if (dx * dx + dy * dy <= radius * radius)
            return true;
    }
    return false;
}

int read16(std::istream &in) {
    unsigned char bytes[2];
    if (!in.read(reinterpret_cast<char *>(bytes), 2))
        throw std::runtime_error("Incomplete span mask");
    return bytes[0] + bytes[1] * 256;
}

void readMask(const fs::path &path, Scene &scene, int width, int height) {
    auto &clip = scene.image;
    std::ifstream in(path, std::ios::binary);
    char magic[4];
    unsigned char binary[32];
    if (!in.read(magic, 4) || std::string(magic, 4) != "DCM1" ||
        !in.read(reinterpret_cast<char *>(binary), 32))
        throw std::runtime_error("Missing or invalid mask: " + clip.id);
    std::ostringstream hash;
    for (const auto b : binary)
        hash << std::hex << std::setfill('0') << std::setw(2) << int(b);
    if (hash.str() != clip.hash || read16(in) != clip.frames)
        throw std::runtime_error("Mask does not match media: " + clip.id);
    clip.masks.resize(clip.frames);
    for (int frame = 0; frame < clip.frames; ++frame) {
        auto &spans = clip.masks[frame];
        const int count = read16(in);
        for (int i = 0; i < count; ++i) {
            const auto y = uint16_t(read16(in)), x = uint16_t(read16(in)), end = uint16_t(read16(in));
            if (y >= height / 2 || x >= end || end > width / 2 ||
                (!spans.empty() && (y < spans.back().y || (y == spans.back().y && x < spans.back().x1))))
                throw std::runtime_error("Invalid mask span: " + clip.id);
            spans.push_back({y, x, end});
        }
        if (spans.empty() == bool(scene.window(frame)))
            throw std::runtime_error("Mask does not cover authored window: " + clip.id);
    }
    if (in.get() != EOF)
        throw std::runtime_error("Unexpected trailing mask bytes: " + clip.id);
}
} // namespace

const Difficulty &difficulty(const std::string &id) {
    static const Difficulty profiles[] = {{"easy", "简单", 5, 15, -1, 24, 0, .4, 1.4, 1.3},
                                          {"normal", "普通", 3, 20, 0, 12, 1, .6, 1., 1.},
                                          {"hard", "困难", 3, 25, 1, 0, 1, .8, .65, .7}};
    for (const auto &profile : profiles)
        if (profile.id == id)
            return profile;
    throw std::runtime_error("Unknown difficulty: " + id);
}

Match::Match(const Encounter &e) : encounter(e), rules(difficulty("normal")) {
    if (!e.selectableDifficulty)
        rules.aimRadius = 0;
}

int Match::health(const Node &node) const {
    return node.hp > 1 ? std::max(1, node.hp + rules.eliteBonus) : node.hp;
}

double Match::playbackRate(int frame) const {
    if (!scene || scene->impact < 0 || frame < scene->warning || frame >= scene->impact)
        return 1.;
    return 1. / (scene->launch >= 0 && frame >= scene->launch ? rules.projectileScale : rules.warningScale);
}

const Window *Scene::window(int frame) const {
    for (const auto &w : windows)
        if (w.begin <= frame && frame < w.end)
            return &w;
    return nullptr;
}

Point Scene::center(int frame) const {
    if (!window(frame))
        return {-1, -1};
    const auto &spans = image.masks.at(frame);
    if (spans.empty())
        return {-1, -1};
    const int row = (spans.front().y + spans.back().y) / 2;
    const Span *best = &spans.front();
    for (const auto &span : spans)
        if (std::abs(int(span.y) - row) < std::abs(int(best->y) - row) ||
            (span.y == best->y && span.x1 - span.x0 > best->x1 - best->x0))
            best = &span;
    return {double(best->x0 + best->x1), 2. * best->y + 1.};
}

Encounter::Encounter(const fs::path &dir) {
    std::ifstream input(dir / "level.json");
    const auto data = Json::parse(input);
    if (data.at("version") != 1 || data.at("fps") != 24)
        throw std::runtime_error("Unsupported Changan encounter version or frame rate");
    width = data.at("size").at(0);
    height = data.at("size").at(1);
    if (width <= 0 || height <= 0 || width > 4096 || height > 4096 || width % 2 || height % 2)
        throw std::runtime_error("Invalid encounter dimensions");
    title = data.at("title");
    first = data.at("first");
    selectableDifficulty = data.value("selectable_difficulty", false);
    location = data.value("location", "朱雀大街  /  上元夜");
    briefing = data.value("briefing", "执灯使巡街，三道妖影陆续现身。");
    cleared = data.value("cleared", "三妖已净");
    if (data.contains("street")) {
        const auto &spec = data.at("street");
        street = Street{spec.at("frames"), spec.at("sha256")};
        if (street->frames < 1 || street->frames > 65535 || street->hash.size() != 64 ||
            street->hash.find_first_not_of("0123456789abcdef") != std::string::npos ||
            !data.value("market_entries", Json::array()).empty())
            throw std::runtime_error("Invalid one-shot street metadata");
    }
    std::set<std::string> nodeIds;
    for (const auto &n : data.at("nodes")) {
        nodes.push_back({n.at("id"), n.at("label"), n.value("flinch", ""), n.at("hp"), n.at("score")});
        if (nodes.back().hp < 1 || nodes.back().score < 0 || nodes.back().id.empty() ||
            !nodeIds.insert(nodes.back().id).second)
            throw std::runtime_error("Invalid node strength or score");
    }
    if (nodes.empty())
        throw std::runtime_error("Empty encounter");
    for (const auto &[id, j] : data.at("clips").items()) {
        auto &s = scenes[id];
        auto &c = s.image;
        c.id = id;
        s.mediaId = j.value("media", id);
        c.next = j.at("next");
        c.frames = j.at("frames");
        c.hash = j.at("sha256");
        s.inAnchor = j.at("in_anchor");
        s.outAnchor = j.at("out_anchor");
        s.launch = j.value("launch_frame", -1);
        s.impact = j.value("impact_frame", -1);
        c.start = j.value("start", 0);
        s.warning = j.value("warning_frame", s.impact < 0 ? -1 : std::max(c.start, s.impact - 14));
        s.minimumDifficulty = j.value("minimum_difficulty", "easy");
        difficulty(s.minimumDifficulty);
        if (s.warning != -1 && (s.warning < c.start || s.warning >= s.impact))
            throw std::runtime_error("Invalid warning frame: " + id);
        if (id.empty() || s.mediaId.empty() ||
            s.mediaId.find_first_not_of("0123456789abcdefghijklmnopqrstuvwxyz_") != std::string::npos ||
            id.find_first_not_of("0123456789abcdefghijklmnopqrstuvwxyz_") != std::string::npos ||
            c.hash.size() != 64 || c.hash.find_first_not_of("0123456789abcdef") != std::string::npos ||
            c.start < 0 || c.start >= c.frames || c.frames > 65535 || s.inAnchor.empty() ||
            s.outAnchor.empty() || s.launch < -1 || s.impact < -1 || s.launch >= c.frames ||
            s.impact >= c.frames || (s.launch >= 0 && s.impact <= s.launch))
            throw std::runtime_error("Invalid clip metadata: " + id);
        int previous = c.start;
        for (const auto &entry : j.value("windows", Json::array())) {
            const std::string kind = entry.at("kind");
            Window w{entry.at("begin"), entry.at("end"), entry.at("node"),
                     kind == "target"       ? Kind::target
                     : kind == "projectile" ? Kind::projectile
                     : kind == "civilian"   ? Kind::civilian
                                            : Kind::none,
                     entry.at("hit")};
            if (w.begin < previous || w.end <= w.begin || w.end > c.frames || w.node < 0 ||
                w.node >= int(nodes.size()) || w.kind == Kind::none ||
                (w.kind == Kind::projectile && (s.launch < 0 || w.begin < s.launch || w.end > s.impact)) ||
                (w.kind == Kind::target && s.impact >= 0 &&
                 w.end > std::max(0, s.launch >= 0 ? s.launch : s.impact)))
                throw std::runtime_error("Invalid window: " + id);
            previous = w.end;
            s.windows.push_back(w);
        }
        if (!s.windows.empty())
            readMask(dir / (id + ".mask"), s, width, height);
    }
    for (const auto &j : data.value("market_entries", Json::array())) {
        MovieEntry e{j.at("source"), j.at("dest"), j.at("take"), j.at("sha256"), j.at("begin"), j.at("end")};
        if (!scenes.contains(e.source) || !scenes.contains(e.destination) || e.file.empty() ||
            e.file.find_first_not_of("0123456789abcdefghijklmnopqrstuvwxyz_") != std::string::npos ||
            e.hash.size() != 64 || e.hash.find_first_not_of("0123456789abcdef") != std::string::npos ||
            e.begin < 0 || e.end <= e.begin || e.end > scenes.at(e.source).image.frames)
            throw std::runtime_error("Invalid market entrance: " + e.file);
        entries.push_back(std::move(e));
    }
    std::set<std::string> reached;
    std::vector<std::string> pending{first};
    bool complete = false;
    while (!pending.empty()) {
        auto id = pending.back();
        pending.pop_back();
        if (id == "@complete") {
            complete = true;
            continue;
        }
        const auto it = scenes.find(id);
        if (it == scenes.end())
            throw std::runtime_error("Unresolved clip: " + id);
        if (!reached.insert(id).second)
            continue;
        pending.push_back(it->second.image.next);
        for (const auto &w : it->second.windows) {
            pending.push_back(w.onHit);
            if (w.kind == Kind::target && nodes[w.node].hp > 1)
                pending.push_back(nodes[w.node].flinch);
        }
    }
    if (!complete || reached.size() != scenes.size())
        throw std::runtime_error("Incomplete Changan clip graph");
    for (const auto &[id, scene] : scenes) {
        if (scene.minimumDifficulty != "easy" &&
            (scene.windows.empty() ||
             !std::all_of(scene.windows.begin(), scene.windows.end(),
                          [](const Window &w) { return w.kind == Kind::civilian; }) ||
             scene.image.next == "@complete" || scenes.at(scene.image.next).minimumDifficulty != "easy"))
            throw std::runtime_error("Optional civilian scene needs a direct return: " + id);
    }
}

const MovieEntry *Encounter::entrance(const Scene &from, const std::string &to, int frame) const {
    for (const auto &e : entries)
        if (e.source == from.image.id && e.destination == to && e.begin <= frame && frame < e.end)
            return &e;
    return nullptr;
}

void Match::enter(const std::string &id) {
    ++generation;
    pending.clear();
    attacked = launched = false;
    if (id == "@complete") {
        if (progress != int(encounter.nodes.size()))
            throw std::runtime_error("Encounter ended before the final target was purified");
        screen = Screen::complete;
    } else {
        scene = &encounter.scenes.at(id);
        if ((scene->minimumDifficulty == "normal" && rules.id == "easy") ||
            (scene->minimumDifficulty == "hard" && rules.id != "hard"))
            scene = &encounter.scenes.at(scene->image.next);
    }
}

void Match::start(int initialEnergy) {
    screen = Screen::play;
    paused = false;
    progress = score = shots = hits = combo = launches = hurts = blocks = reloads = 0;
    bestCombo = 0;
    elapsed = 0;
    targetOpened = -1;
    energy = initialEnergy;
    lives = rules.lives;
    civilianHits = 0;
    arrows = 8;
    reloadLeft = frozenUntil = 0;
    hp = health(encounter.nodes.front());
    enter(encounter.first);
}

void Match::title() {
    ++generation;
    screen = Screen::title;
    paused = false;
    pending.clear();
    scene = nullptr;
}

Cue Match::input(Point position, int gen, int frame, bool thunder, double now) {
    if (!interactive() || gen != generation || reloadLeft > 0)
        return Cue::none;
    const Window *w = scene->window(frame);
    if (!active(w))
        return Cue::none;
    if (thunder && (energy < rules.charge || w->kind != Kind::target))
        return Cue::none;
    if (!thunder && arrows == 0)
        return Cue::empty;
    if (thunder) {
        energy = 0;
    } else {
        --arrows;
        ++shots;
        if (!coversWithAssist(scene->image, frame, position,
                              w->kind == Kind::civilian ? 0 : rules.aimRadius)) {
            combo = 0;
            energy = std::max(0, energy - 2);
            return Cue::miss;
        }
        if (w->kind == Kind::civilian) {
            ++civilianHits;
            combo = energy = 0;
            score = std::max(0, score - 100);
            lives -= rules.civilianDamage;
            if (lives == 0) {
                ++generation;
                screen = Screen::failed;
            } else {
                pending = w->onHit;
                frozenUntil = now + .05;
            }
            return Cue::civilian;
        }
        ++hits;
        ++combo;
        bestCombo = std::max(bestCombo, combo);
        energy = std::min(rules.charge, energy + 1);
    }
    if (w->kind == Kind::projectile) {
        ++blocks;
        score += 150;
        frozenUntil = now + .050;
        pending = w->onHit;
        return Cue::intercept;
    }
    const Node &n = encounter.nodes[progress];
    hp -= thunder ? 2 : 1;
    frozenUntil = now + (n.hp > 1 ? .120 : .050);
    if (hp > 0) {
        pending = n.flinch;
        return thunder ? Cue::special : Cue::hit;
    }
    if (encounter.selectableDifficulty) {
        const double reaction = targetOpened < 0 ? 0 : std::max(0., elapsed - targetOpened);
        const double speedBonus = 1. + .5 * std::max(0., 1. - reaction / 1.8);
        const double comboBonus = std::min(3., 1. + combo * .05);
        score += int(std::lround(n.score * speedBonus * comboBonus));
    } else {
        score += n.score;
    }
    targetOpened = -1;
    ++progress;
    hp = progress < int(encounter.nodes.size()) ? health(encounter.nodes[progress]) : 0;
    pending = w->onHit;
    return thunder ? Cue::special : Cue::purify;
}

Cue Match::present(int gen, int frame) {
    if (!interactive() || gen != generation || frame < scene->image.start)
        return Cue::none;
    const auto *window = scene->window(frame);
    if (targetOpened < 0 && active(window) && window->kind == Kind::target)
        targetOpened = elapsed;
    if (!launched && scene->launch >= 0 && frame >= scene->launch) {
        launched = true;
        ++launches;
    }
    if (!attacked && scene->impact >= 0 && frame >= scene->impact) {
        attacked = true;
        ++hurts;
        energy = combo = 0;
        if (--lives == 0) {
            ++generation;
            screen = Screen::failed;
        }
        return Cue::hurt;
    }
    if (frame >= scene->image.frames - 1)
        enter(scene->image.next);
    return Cue::none;
}

Cue Match::tick(double dt, double now) {
    if (paused || screen != Screen::play)
        return Cue::none;
    elapsed += dt;
    if (!pending.empty()) {
        if (now >= frozenUntil) {
            auto next = pending;
            enter(next);
        }
        return Cue::none;
    }
    if (reloadLeft > 0) {
        reloadLeft = std::max(0., reloadLeft - dt);
        if (reloadLeft == 0) {
            arrows = 8;
            ++reloads;
            return Cue::ready;
        }
    }
    return Cue::none;
}

Cue Match::reload() {
    if (!interactive() || reloadLeft > 0 || arrows == 8)
        return Cue::none;
    reloadLeft = rules.reloadSeconds;
    return Cue::reload;
}
} // namespace ca
