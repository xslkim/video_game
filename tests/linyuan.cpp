#include "changan_game.hpp"
#include <iostream>
#include <random>

using namespace ca;

namespace {
void require(bool value, const char *why) {
    if (!value)
        throw std::runtime_error(why);
}

// A tiny media-free encounter, with the same hashed DCM1 masks as a release level.
struct Fixture {
    fs::path folder;
    Json level;

    static void word(std::ostream &s, int n) {
        s.put(char(n));
        s.put(char(n >> 8));
    }

    void mask(const std::string &file, int first, int last, int x0, int x1) {
        std::ofstream s(folder / file, std::ios::binary);
        s.write("DCM1", 4);
        std::array<char, 32> hash{};
        s.write(hash.data(), hash.size());
        word(s, 6);
        for (int f = 0; f < 6; ++f) {
            const bool active = f >= first && f < last;
            word(s, active ? 1 : 0);
            if (active) {
                word(s, 8);
                word(s, x0);
                word(s, x1);
            }
        }
    }

    Json &scene(const std::string &id, const std::string &next) {
        return level["clips"][id] = {{"next", next}, {"sha256", std::string(64, '0')},
                                     {"in_anchor", "plate"}, {"out_anchor", "plate"}, {"frames", 6}};
    }

    void save() const {
        std::ofstream(folder / "level.json") << level.dump();
    }

    Fixture() {
        folder = fs::temp_directory_path() / ("linyuan-rules-" + std::to_string(std::random_device{}()));
        if (!fs::create_directory(folder))
            throw std::runtime_error("Unable to allocate temporary encounter directory");
        level = {{"version", 1}, {"fps", 24}, {"size", {128, 64}}, {"title", "rules test"},
                 {"first", "lion"}, {"ruleset", "linyuan"}};
        level["materials"] = std::vector<std::vector<std::string>>(36, std::vector<std::string>(64, "earth"));
        level["materials"][35][63] = "water";
        level["nodes"] = Json::parse(R"([
            {"id":"lion","label":"lion","hp":1,"score":100,"weak_bonus":50},
            {"id":"elite","label":"elite","hp":2,"score":700,"flinch":"flinch"},
            {"id":"rope","label":"rope","hp":1,"score":400,"fixed_score":true,"kills":2}
        ])");
        auto &lion = scene("lion", "lion");
        lion["weak_mask"] = true;
        lion["allow_early_miss"] = true;
        lion["impact_frame"] = 5;
        for (int frame = 1; frame < 5; ++frame)
            lion["material_transforms"].push_back({{"frame", frame}, {"to_plate", {1, 0, 100, 0, 1, 0, 0, 0, 1}}});
        lion["windows"] = Json::parse(R"([
            {"begin":1,"end":3,"node":0,"kind":"target","hit":"early"},
            {"begin":3,"end":5,"node":0,"kind":"target","hit":"late"}
        ])");
        mask("lion.mask", 1, 5, 8, 24);
        mask("lion.weak.mask", 2, 5, 12, 14);
        scene("early", "needles");
        scene("late", "needles");
        auto &needles = scene("needles", "needles");
        needles["launch_frame"] = 1;
        needles["impact_frame"] = 4;
        needles["end"] = 5;
        needles["windows"] = Json::parse(R"([{"begin":1,"end":4,"node":1,"kind":"projectile","hit":"core"}])");
        mask("needles.mask", 1, 4, 8, 12);
        auto &core = scene("core", "needles");
        core["start"] = 5;
        core["hold_seconds"] = 2.;
        core["windows"] = Json::parse(R"([{"begin":5,"end":6,"node":1,"kind":"target","hit":"rope","weak":true}])");
        mask("core.mask", 5, 6, 30, 32);
        scene("flinch", "needles");
        auto &rope = scene("rope", "rope");
        rope["impact_frame"] = 5;
        rope["windows"] = Json::parse(R"([{"begin":1,"end":5,"node":2,"kind":"target","hit":"@complete"}])");
        mask("rope.mask", 1, 5, 8, 12);
        save();
    }

    ~Fixture() {
        std::error_code ignored;
        fs::remove_all(folder, ignored);
    }
};

void checkRules(Fixture &f) {
    const Encounter encounter(f.folder);
    require(encounter.materialAt({0, 0}) == "earth" && encounter.materialAt({127, 63}) == "water" &&
                encounter.materialAt({128, 63}).empty() && encounter.materialAt({-1, 0}).empty(),
            "Material grid selected the wrong source cell");
    const auto &moving = encounter.scenes.at("lion");
    require(encounter.materialAt(moving, 1, {27, 63}) == "water" &&
                encounter.materialAt(moving, 0, {27, 63}).empty() &&
                encounter.materialAt(moving, 1, {127, 63}).empty(), "Moving camera material projection");
    Match g(encounter);
    auto present = [&](int frame) { return g.present(g.generation, frame); };
    auto fire = [&](int frame, double x, double now) {
        return g.input({x, 16}, g.generation, frame, false, now);
    };
    g.start();
    require(fire(0, 24, 0) == Cue::miss && g.arrows == 7 && !g.lastWeakHit, "early scan lacked a cost");
    require(g.reload(0.) == Cue::reload && std::abs(g.reloadLeft-.215)<.00001, "one sword recall");
    require(g.tick(.325, .010) == Cue::none && std::abs(g.reloadLeft-.205)<.00001, "pre-input wall time shortened the recall");
    require(g.tick(.206,.216) == Cue::ready && g.arrows == 8, "partial recall did not restore the rack");
    require(fire(1, 15, 0) == Cue::purify && !g.lastWeakHit && g.score == 158,
            "assisted body hit awarded weak point");
    require(g.pending == "early" && g.kills == 1, "early hit did not pick its cut");
    g.start();
    present(1);
    require(fire(3, 24, 0) == Cue::purify && g.lastWeakHit && g.score == 236 && g.pending == "late",
            "direct shoulder hit or late cut failed");
    require(fire(3, 24, .02) == Cue::none && g.arrows == 8 && g.weakReturns == 1, "weak refund or hit stop");
    g.tick(.099, .099);
    require(g.pending == "late", "weak point hit stop too short");
    g.tick(.002, .101);
    present(5);
    require(g.scene->image.id == "needles", "ordinary kill did not advance");
    require(fire(1, 60, 1.) == Cue::miss && g.hp == 2, "covered core took damage");
    require(fire(2, 18, 1.) == Cue::intercept && g.blocks == 1 && g.frozenUntil == 1.070,
            "first intercept failed");
    g.tick(.071, 1.071);
    present(5);
    require(fire(5, 60, 2.) == Cue::hit && g.hp == 1 && g.lastWeakHit && g.frozenUntil == 2.100,
            "first core hit failed");
    g.tick(.101, 2.101);
    present(5);
    require(g.scene->image.id == "needles" && g.hp == 1, "first core hit skipped mandatory refire");
    const int reward = g.score;
    require(fire(2, 18, 2.2) == Cue::intercept && g.score == reward+150, "second-round intercept");
    g.tick(.071, 2.271);
    present(5);
    const int before = g.score, combo = g.combo;
    g.tick(1.80, 4.);
    g.paused = true;
    g.tick(3., 7.);
    g.paused = false;
    g.tick(.19, 7.19);
    require(g.scene->image.id == "core" && g.hp == 1, "exposure window did not pause");
    g.tick(.02, 7.21);
    require(g.scene->image.id == "needles" && g.lives == 3, "core timeout damaged player");
    require(fire(1, 18, 8.) == Cue::intercept && g.score == before && g.combo == combo &&
                g.blocks == 3 && g.hits == 5,
            "repeat intercept award or hit count");
    g.tick(.071, 8.071);
    present(5);
    require(fire(5, 60, 9.) == Cue::purify && g.kills == 2 && g.frozenUntil == 9.100,
            "elite core finisher did not register a precise weak-point hit");
    g.tick(.101, 9.101);
    const int eliteScore = g.score;
    require(g.progress == 2 && fire(1, 18, 10.) == Cue::purify && g.kills == 4 &&
                g.score == eliteScore + 400, "rope must count both victims at fixed score");
    g.tick(.071, 10.071);
    require(g.screen == Screen::complete && g.hits == 7 && g.shots == 8 && g.weakReturns == 3, "final statistics");
}

void checkInvalidWeakMask(Fixture &f) {
    f.mask("lion.weak.mask", 2, 5, 22, 26);
    try {
        Encounter invalid(f.folder);
    } catch (const std::runtime_error &) {
        return;
    }
    throw std::runtime_error("Shoulder extended outside body but loaded");
}

void checkMissAndRestart(const Encounter &e) {
    Match g(e);
    g.start();
    g.progress = 1;
    g.hp = 1;
    g.enter("needles");
    const int gen = g.generation;
    require(g.present(gen, 4) == Cue::hurt && g.present(gen, 4) == Cue::none &&
                g.lives == 2 && g.hurts == 1 && g.hp == 1, "missed cluster caused repeated damage");
    g.tick(.04, .04);
    g.tick(.085, .125);
    require(g.isFrozen() && !g.interactive(), "damage did not freeze its source frame");
    g.paused = true;
    g.tick(2., 2.125);
    require(g.isFrozen(), "pause consumed damage stop");
    g.paused = false;
    g.tick(.006, 2.131);
    g.present(gen, 4);
    require(g.scene->image.id == "needles" && g.hp == 1, "missed cluster opened core or discarded elite HP");
    g.enter("core");
    g.arrows = 0;
    require(g.input({60, 16}, g.generation, 5, false, 1.) == Cue::empty && g.shots == 0,
            "empty trigger counted as shot");
    require(g.reload(1.) == Cue::reload && g.input({60, 16}, g.generation, 5, false, 1.) == Cue::none,
            "reload allowed fire");
    g.tick(.59, 1.59);
    require(g.arrows == 0, "recalled swords returned early");
    require(g.tick(.02, 1.61) == Cue::ready && g.arrows == 8, "recall failed");
    g.start();
    require(g.kills == 0 && !g.interceptRewarded && g.hits == 0 && g.hurts == 0 && g.progress == 0,
            "stale counters after replay");
}

void checkArmor(Fixture &fixture) {
    auto &node = fixture.level["nodes"][0];
    const auto initial = node;
    node["hp"] = node["weak_damage"] = 2;
    node["flinch"] = "lion";
    fixture.save();
    const Encounter e(fixture.folder);
    Match g(e);
    g.start();
    require(g.input({19,16},g.generation,2,false,0) == Cue::hit && g.hp == 1 && g.arrows == 7 &&
            g.isFrozen(), "first white armor hit must chip without cutting the clip");
    g.tick(.03,.03);
    g.tick(.062,.092);
    require(g.input({19,16},g.generation,3,false,.1) == Cue::purify && g.arrows == 6 &&
            !g.weakReturns, "second white armor hit must break it");
    g.start();
    require(g.input({25,16},g.generation,3,false,0) == Cue::purify && g.arrows == 8 &&
            g.weakReturns == 1 && g.shots == 1, "precise shoulder hit must bypass armor and return its sword");
    g.start();
    g.progress = 1; g.hp = 2; g.enter("core");
    require(g.input({57,16},g.generation,5,false,0) == Cue::hit && g.arrows == 7 && !g.lastWeakHit,
            "aim assist through the edge of a core incorrectly returned a sword");
    node = initial;
    fixture.save();
}

void checkFeedbackSchema(Fixture &f) {
    f.level["nodes"][0]["material"] = "feather";
    f.level["nodes"][0]["tier"] = 2;
    f.level["clips"]["lion"]["attack"] = "collision";
    f.save();
    const Encounter valid(f.folder);
    require(valid.nodes[0].material == "feather" && valid.nodes[0].tier == 2 &&
                valid.scenes.at("lion").attack == "collision",
            "Failed to parse data-driven node material, tier or clip attack");

    f.level["nodes"][0]["material"] = "wood";
    f.save();
    bool badMaterial = false;
    try {
        Encounter bad(f.folder);
    } catch (const std::exception &) {
        badMaterial = true;
    }
    require(badMaterial, "Invalid node material must be rejected");
    f.level["nodes"][0].erase("material");
    f.level["nodes"][0].erase("tier");

    f.level["clips"]["lion"]["attack"] = "laser";
    f.save();
    bool badAttack = false;
    try {
        Encounter bad(f.folder);
    } catch (const std::exception &) {
        badAttack = true;
    }
    require(badAttack, "Invalid clip attack must be rejected");
    f.level["clips"]["lion"].erase("attack");
    f.save();
}

void checkChanganDefaults(Fixture &f) {
    f.level.erase("ruleset");
    f.level["clips"]["core"].erase("hold_seconds");
    f.level["clips"]["lion"].erase("weak_mask");
    f.save();
    const Encounter legacy(f.folder);
    Match g(legacy);
    g.start();
    require(g.rules.aimRadius == 0, "legacy prototype picked up Linyuan aim assist");
    require(g.input({24, 16}, g.generation, 2, false, 1.) == Cue::purify &&
                g.score == 100 && g.frozenUntil == 1.050, "legacy scoring or hit stop changed");
    g.tick(.06, 1.06);
    g.present(g.generation, 5);
    for (int i = 0; i < 2; ++i) {
        require(g.input({18, 16}, g.generation, 2, false, 2. + i) == Cue::intercept,
                "legacy intercept rejected");
        g.tick(.06, 2.06 + i);
        g.present(g.generation, 5);
    }
    require(g.score == 400 && g.combo == 3 && g.energy == 3,
            "legacy repeat intercept or special charge changed");
}
} // namespace

int main() {
    try {
        Fixture f;
        checkRules(f);
        checkArmor(f);
        checkFeedbackSchema(f);
        checkMissAndRestart(Encounter(f.folder));
        checkInvalidWeakMask(f);
        checkChanganDefaults(f);
        std::cout << "Linyuan encounter rules passed\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
