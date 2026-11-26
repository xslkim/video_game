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

// A mask can contain independent targets, such as a fox's forehead and tail hub.
std::vector<WeakSpot> findWeakSpots(const std::vector<Span> &spans) {
    // An occluding armor edge can split the glint on one canister by a few mask pixels.
    constexpr int maxGap = 4;
    std::vector<WeakSpot> spots;
    std::vector<bool> seen(spans.size());
    std::vector<size_t> connected;
    for (size_t seed = 0; seed < spans.size(); ++seed) {
        if (seen[seed])
            continue;
        seen[seed] = true;
        connected.assign(1, seed);
        int left = spans[seed].x0, right = spans[seed].x1;
        int top = spans[seed].y, bottom = top;
        for (size_t i = 0; i < connected.size(); ++i) {
            const auto &s = spans[connected[i]];
            left = std::min(left, int(s.x0));
            right = std::max(right, int(s.x1));
            bottom = std::max(bottom, int(s.y));
            auto n = std::lower_bound(spans.begin(), spans.end(), int(s.y) - maxGap,
                                      [](const Span &span, int y) { return span.y < y; });
            for (; n != spans.end() && n->y <= s.y + maxGap; ++n) {
                const auto index = size_t(n - spans.begin());
                const int dx = std::max({0, int(n->x0) - s.x1 + 1, int(s.x0) - n->x1 + 1});
                const int dy = int(n->y) - s.y;
                if (!seen[index] && dx * dx + dy * dy <= maxGap * maxGap) {
                    seen[index] = true;
                    connected.push_back(index);
                }
            }
        }
        // Put the guide on an actual covered pixel even for a clipped or concave component.
        const Point center{double(left + right), double(top + bottom + 1)};
        Point nearest{};
        double best = 1e30;
        for (auto index : connected) {
            const auto &s = spans[index];
            const Point onMask{std::clamp(center.x, 2. * s.x0 + 1, 2. * s.x1 - 1), 2. * s.y + 1};
            const auto dx = center.x - onMask.x, dy = center.y - onMask.y;
            if (dx * dx + dy * dy < best) {
                best = dx * dx + dy * dy;
                nearest = onMask;
            }
        }
        spots.push_back({nearest, 2. * (bottom - top + 1)});
    }
    return spots;
}

void readMask(const fs::path &path, Scene &scene, int width, int height, bool weak = false) {
    const auto &clip = scene.image;
    auto &rows = weak ? scene.weakArea.masks : scene.image.masks;
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
    rows.resize(clip.frames);
    bool hasSpans = false;
    for (int frame = 0; frame < clip.frames; ++frame) {
        auto &spans = rows[frame];
        const int count = read16(in);
        for (int i = 0; i < count; ++i) {
            const auto y = uint16_t(read16(in)), x = uint16_t(read16(in)), end = uint16_t(read16(in));
            if (y >= height / 2 || x >= end || end > width / 2 ||
                (!spans.empty() && (y < spans.back().y || (y == spans.back().y && x < spans.back().x1))))
                throw std::runtime_error("Invalid mask span: " + clip.id);
            spans.push_back({y, x, end});
        }
        const Window *window = scene.window(frame);
        if (!weak && spans.empty() == bool(window))
            throw std::runtime_error("Mask does not cover authored window: " + clip.id);
        if (weak && !spans.empty()) {
            if (!window || window->kind != Kind::target)
                throw std::runtime_error("Weak mask outside target window: " + clip.id);
            const auto &body = clip.masks[frame];
            auto covers = body.begin();
            for (const auto &span : spans) {
                unsigned x = span.x0;
                while (covers != body.end() &&
                       (covers->y < span.y || (covers->y == span.y && covers->x1 <= x)))
                    ++covers;
                while (x < span.x1 && covers != body.end() && covers->y == span.y && covers->x0 <= x) {
                    x = covers->x1;
                    if (x < span.x1)
                        ++covers;
                }
                if (x < span.x1)
                    throw std::runtime_error("Weak mask exceeds body: " + clip.id);
            }
        }
        hasSpans = hasSpans || !spans.empty();
    }
    if (weak && !hasSpans)
        throw std::runtime_error("Empty weak mask: " + clip.id);
    if (weak)
        for (const auto &spans : rows)
            scene.weakSpots.push_back(findWeakSpots(spans));
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
    if (!e.selectableDifficulty && !e.linyuan)
        rules.aimRadius = 0;
}

int Match::health(const Node &node) const {
    if (encounter.linyuan)
        return node.hp;
    return node.hp > 1 ? std::max(1, node.hp + rules.eliteBonus) : node.hp;
}

double Match::playbackRate(int frame) const {
    if (!scene)
        return 1.;
    if (scene->impact < 0 || frame < scene->warning || frame >= scene->impact)
        return scene->speed;
    return scene->speed / (scene->launch >= 0 && frame >= scene->launch ? rules.projectileScale : rules.warningScale);
}

const Window *Scene::window(int frame) const {
    for (const auto &w : windows)
        if (w.begin <= frame && frame < w.end)
            return &w;
    return nullptr;
}

bool Scene::aimCovers(int frame, Point position, int radius) const {
    const auto *w = window(frame);
    return w && coversWithAssist(image, frame, position, w->kind == Kind::civilian ? 0 : radius);
}

bool Scene::weakAt(int frame, Point position) const {
    const auto *w = window(frame);
    return w && w->kind == Kind::target &&
           (w->weak ? image.covers(frame, position) : weakArea.covers(frame, position));
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
    if (data.contains("materials")) {
        materials = data.at("materials").get<decltype(materials)>();
        const std::set<std::string> names{"air", "water", "stone", "earth", "bamboo", "metal"};
        if (materials.size() != 36 || std::any_of(materials.begin(), materials.end(), [&](const auto &row) {
                return row.size() != 64 || std::any_of(row.begin(), row.end(), [&](const auto &cell) {
                    return !names.contains(cell);
                });
            }))
            throw std::runtime_error("Invalid 64x36 encounter materials");
    }
    title = data.at("title");
    first = data.at("first");
    const auto ruleset = data.value("ruleset", std::string("changan"));
    if (ruleset != "linyuan" && ruleset != "changan")
        throw std::runtime_error("Unsupported encounter ruleset: " + ruleset);
    linyuan = ruleset == "linyuan";
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
    const std::set<std::string> nodeMaterials{"", "ceramic", "feather", "vine", "crystal", "metal", "phantom"};
    const std::set<std::string> attackKinds{"", "claw", "collision", "blast"};
    std::set<std::string> nodeIds;
    for (const auto &n : data.at("nodes")) {
        nodes.push_back({n.at("id"), n.at("label"), n.value("flinch", ""), n.at("hp"), n.at("score"),
                         n.value("weak_bonus", 0), n.value("kills", 1), n.value("fixed_score", false),
                         n.value("weak_damage", 1), n.value("material", ""), n.value("tier", 0)});
        if (nodes.back().hp < 1 || nodes.back().score < 0 || nodes.back().weakBonus < 0 ||
            nodes.back().kills < 1 || nodes.back().weakDamage < 1 || nodes.back().weakDamage > nodes.back().hp ||
            !nodeMaterials.contains(nodes.back().material) || nodes.back().tier < 0 || nodes.back().tier > 3 ||
            nodes.back().id.empty() ||
            !nodeIds.insert(nodes.back().id).second)
            throw std::runtime_error("Invalid node strength or score");
    }
    if (nodes.empty())
        throw std::runtime_error("Empty encounter");
    Json threatTracks = Json::object();
    if (linyuan && fs::is_regular_file(dir / "threat_glows.json")) {
        std::ifstream tracks(dir / "threat_glows.json");
        threatTracks = Json::parse(tracks);
    }
    for (const auto &[id, j] : data.at("clips").items()) {
        auto &s = scenes[id];
        auto &c = s.image;
        c.id = id;
        s.mediaId = j.value("media", id);
        s.attack = j.value("attack", "");
        if (!attackKinds.contains(s.attack))
            throw std::runtime_error("Invalid clip attack: " + id);
        c.next = j.at("next");
        c.frames = j.at("frames");
        c.hash = j.at("sha256");
        s.inAnchor = j.at("in_anchor");
        s.outAnchor = j.at("out_anchor");
        s.launch = j.value("launch_frame", -1);
        s.impact = j.value("impact_frame", -1);
        s.holdSeconds = j.value("hold_seconds", 0.);
        s.allowEarlyMiss = j.value("allow_early_miss", false);
        s.speed = j.value("speed", 1.);
        if (!std::isfinite(s.speed) || s.speed <= 0 || s.speed > 2)
            throw std::runtime_error("Invalid action speed: " + id);
        c.start = j.value("start", 0);
        s.end = j.value("end", c.frames);
        s.warning = j.value("warning_frame", s.impact < 0 ? -1 : std::max(c.start, s.impact - 14));
        s.minimumDifficulty = j.value("minimum_difficulty", "easy");
        if (s.impact >= 0 && threatTracks.contains(s.mediaId)) {
            const auto &track = threatTracks.at(s.mediaId);
            if (track.at("sha256") != c.hash)
                throw std::runtime_error("Stale threat glow annotations: " + id);
            for (const auto &entry : track.at("points")) {
                const int f = entry.at(0);
                if ((entry.size() != 3 && entry.size() != 5) || f < 0 || f >= c.frames)
                    throw std::runtime_error("Invalid threat glow anchor: " + id);
                for (size_t i = 0; 2 * i + 2 < entry.size(); ++i) {
                    const Point p{entry.at(2 * i + 1), entry.at(2 * i + 2)};
                    if (p.x < 0 || p.x >= width || p.y < 0 || p.y >= height ||
                        !s.threatTracks[i].emplace(f, p).second)
                        throw std::runtime_error("Invalid threat glow position: " + id);
                }
            }
        }
        difficulty(s.minimumDifficulty);
        if (s.warning != -1 && (s.warning < c.start || s.warning >= s.impact))
            throw std::runtime_error("Invalid warning frame: " + id);
        if (id.empty() || s.mediaId.empty() ||
            s.mediaId.find_first_not_of("0123456789abcdefghijklmnopqrstuvwxyz_") != std::string::npos ||
            id.find_first_not_of("0123456789abcdefghijklmnopqrstuvwxyz_") != std::string::npos ||
            c.hash.size() != 64 || c.hash.find_first_not_of("0123456789abcdef") != std::string::npos ||
            c.start < 0 || c.start >= s.end || s.end > c.frames || c.frames > 65535 || s.inAnchor.empty() ||
            s.outAnchor.empty() || s.launch < -1 || s.impact < -1 || s.launch >= s.end || (s.launch >= 0 && s.launch < c.start) ||
            s.impact >= s.end || (s.impact >= 0 && s.impact < c.start) || (s.launch >= 0 && s.impact <= s.launch))
            throw std::runtime_error("Invalid clip metadata: " + id);
        int previous = c.start;
        for (const auto &entry : j.value("windows", Json::array())) {
            const std::string kind = entry.at("kind");
            Window w{entry.at("begin"), entry.at("end"), entry.at("node"),
                     kind == "target"       ? Kind::target
                     : kind == "projectile" ? Kind::projectile
                     : kind == "civilian"   ? Kind::civilian
                                            : Kind::none,
                     entry.at("hit"), entry.value("weak", false)};
            if (w.begin < previous || w.end <= w.begin || w.end > s.end || w.node < 0 ||
                w.node >= int(nodes.size()) || w.kind == Kind::none || (w.weak && w.kind != Kind::target) ||
                (w.kind == Kind::projectile && (s.launch < 0 || w.begin < s.launch || w.end > s.impact)) ||
                (w.kind == Kind::target && s.impact >= 0 &&
                 w.end > std::max(0, s.launch >= 0 ? s.launch : s.impact)))
                throw std::runtime_error("Invalid window: " + id);
            previous = w.end;
            s.windows.push_back(w);
        }
        if (s.holdSeconds < 0 || (s.holdSeconds > 0 &&
            (!linyuan || c.start != c.frames - 1 || s.impact >= 0 || s.windows.size() != 1 ||
             s.windows[0].kind != Kind::target || !s.window(c.start))))
            throw std::runtime_error("Hold needs an exposed target in the final frame: " + id);
        for (const auto &event : j.value("voice_cues", Json::array())) {
            VoiceCue cue{event.at("frame"), event.at("voice"), event.at("subtitle"),
                         event.value("priority", 1)};
            const auto separator = cue.voice.find('/');
            if (cue.frame < c.start || cue.frame >= s.end || cue.priority < 0 || cue.priority > 2 ||
                cue.subtitle.empty() || separator == 0 || separator == std::string::npos ||
                separator + 1 == cue.voice.size() || cue.voice.rfind('/') != separator ||
                cue.voice.find_first_not_of("abcdefghijklmnopqrstuvwxyz_0123456789/") != std::string::npos ||
                (!s.voiceCues.empty() && cue.frame < s.voiceCues.back().frame))
                throw std::runtime_error("Invalid encounter voice cue: " + id);
            s.voiceCues.push_back(std::move(cue));
        }
        for (const auto &pose : j.value("material_transforms", Json::array())) {
            const int frame = pose.at("frame");
            const auto matrix = pose.at("to_plate").get<std::array<double, 9>>();
            if (!s.window(frame) || !std::all_of(matrix.begin(), matrix.end(), [](double x) { return std::isfinite(x); }) ||
                !s.materialTransforms.emplace(frame, matrix).second)
                throw std::runtime_error("Invalid source-to-plate material transform: " + id);
        }
        if (!s.materialTransforms.empty()) {
            for (const auto &w : s.windows)
                for (int f = w.begin; f < w.end; ++f)
                    if (!s.materialTransforms.contains(f))
                        throw std::runtime_error("Missing source-to-plate material transform: " + id);
        }
        if (!s.windows.empty())
            readMask(dir / (id + ".mask"), s, width, height);
        if (j.value("weak_mask", false))
            readMask(dir / (id + ".weak.mask"), s, width, height, true);
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

std::string Encounter::materialAt(Point point) const {
    if (materials.empty() || !(point.x >= 0 && point.x < width && point.y >= 0 && point.y < height))
        return {};
    return materials[int(point.y * 36 / height)][int(point.x * 64 / width)];
}

std::string Encounter::materialAt(const Scene &scene, int frame, Point point) const {
    if (scene.materialTransforms.empty())
        return materialAt(point);
    const auto found = scene.materialTransforms.find(frame);
    if (found == scene.materialTransforms.end() ||
        !(point.x >= 0 && point.x < width && point.y >= 0 && point.y < height))
        return {};
    const auto &m = found->second;
    const auto z = m[6] * point.x + m[7] * point.y + m[8];
    if (std::abs(z) < 1e-9)
        return {};
    return materialAt({(m[0] * point.x + m[1] * point.y + m[2]) / z,
                       (m[3] * point.x + m[4] * point.y + m[5]) / z});
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
    if (encounter.linyuan)
        targetOpened = -1;
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
    bestCombo = kills = weakReturns = 0;
    interceptRewarded = lastWeakHit = false;
    elapsed = 0;
    targetOpened = -1;
    energy = initialEnergy;
    lives = rules.lives;
    civilianHits = 0;
    arrows = 8;
    reloadStartedAt = reloadLeft = frozenUntil = 0;
    hurtFreezeLeft = 0;
    hurtFreezeStarted = false;
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
    const bool early = encounter.linyuan && scene->allowEarlyMiss && !thunder && !scene->windows.empty() &&
                       frame >= scene->image.start && frame < scene->windows.front().begin &&
                       scene->windows.front().node == progress;
    if (!active(w) && !early)
        return Cue::none;
    if (thunder && (encounter.linyuan || energy < rules.charge || w->kind != Kind::target))
        return Cue::none;
    lastWeakHit = false;
    if (!thunder && arrows == 0)
        return Cue::empty;
    if (thunder) {
        energy = 0;
    } else {
        --arrows;
        ++shots;
        if (early || !scene->aimCovers(frame, position, rules.aimRadius)) {
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
        if (!encounter.linyuan || w->kind != Kind::projectile || !interceptRewarded) {
            ++combo;
            bestCombo = std::max(bestCombo, combo);
            if (!encounter.linyuan)
                energy = std::min(rules.charge, energy + 1);
        }
    }
    if (w->kind == Kind::projectile) {
        ++blocks;
        if (!encounter.linyuan || !interceptRewarded)
            score += 150;
        interceptRewarded = true;
        frozenUntil = now + (encounter.linyuan ? .070 : .050);
        pending = w->onHit;
        return Cue::intercept;
    }
    const Node &n = encounter.nodes[progress];
    lastWeakHit = encounter.linyuan ? scene->weakAt(frame, position) : w->weak || scene->weakAt(frame, position);
    if (encounter.linyuan && lastWeakHit) {
        ++arrows;
        ++weakReturns;
    }
    hp -= thunder ? 2 : lastWeakHit ? n.weakDamage : 1;
    frozenUntil = now + (n.hp > 1 ? .120 : .050);
    if (encounter.linyuan) {
        const bool eliteFinish = n.hp > 1 && n.weakDamage == 1;
        frozenUntil = now + (lastWeakHit ? .100 : hp > 0 ? .060 : eliteFinish ? .140 : .070);
    }
    if (hp > 0) {
        if (encounter.linyuan && n.flinch == scene->image.id) {
            // Cracked white armor stays in the shot at the actual impact frame.
            hurtFreezeLeft = frozenUntil - now;
            hurtFreezeStarted = true;
        } else {
            pending = n.flinch;
            if (encounter.linyuan)
                interceptRewarded = false;
        }
        return thunder ? Cue::special : Cue::hit;
    }
    const int baseScore = n.score + (lastWeakHit ? n.weakBonus : 0);
    if ((encounter.linyuan || encounter.selectableDifficulty) && !n.fixedScore) {
        const double reaction = targetOpened < 0 ? 0 : std::max(0., elapsed - targetOpened);
        const double speedBonus = 1. + .5 * std::max(0., 1. - reaction / 1.8);
        const double comboBonus = std::min(3., 1. + combo * .05);
        score += int(std::lround(baseScore * speedBonus * comboBonus));
    } else {
        score += baseScore;
    }
    kills += n.kills;
    interceptRewarded = false;
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
        } else if (encounter.linyuan) {
            hurtFreezeLeft = .090;
            hurtFreezeStarted = true;
        }
        return Cue::hurt;
    }
    if (scene->holdSeconds == 0 && frame >= scene->end - 1)
        enter(scene->image.next);
    return Cue::none;
}

Cue Match::tick(double dt, double now) {
    if (paused || screen != Screen::play)
        return Cue::none;
    elapsed += dt;
    if (isFrozen()) {
        // present() runs just before tick(). Its first dt precedes the impact.
        if (!hurtFreezeStarted)
            hurtFreezeLeft = std::max(0., hurtFreezeLeft - dt);
        hurtFreezeStarted = false;
        return Cue::none;
    }
    if (!pending.empty()) {
        if (now >= frozenUntil) {
            auto next = pending;
            enter(next);
        }
        return Cue::none;
    }
    if (scene->holdSeconds > 0 && targetOpened >= 0 && elapsed >= targetOpened + scene->holdSeconds)
        enter(scene->image.next);
    if (reloadLeft > 0) {
        // The first interval can include decoding time before the input arrived.
        const double recallStep = encounter.linyuan ? std::clamp(now - reloadStartedAt, 0., dt) : dt;
        reloadLeft = std::max(0., reloadLeft - recallStep);
        if (reloadLeft == 0) {
            arrows = 8;
            ++reloads;
            return Cue::ready;
        }
    }
    return Cue::none;
}

Cue Match::reload(double now) {
    if (!interactive() || reloadLeft > 0 || arrows == 8)
        return Cue::none;
    reloadStartedAt = now;
    reloadLeft = encounter.linyuan ? .16 + .055 * (8 - arrows) : rules.reloadSeconds;
    return Cue::reload;
}
} // namespace ca
