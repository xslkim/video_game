#include "changan_game.hpp"
#include "changan_record.hpp"
#include "changan_story.hpp"
#include "gamepad_input.hpp"
#include "linyuan_feedback.hpp"
#include "sound.hpp"
#include "tvgun.hpp"
#include "ui.hpp"
#include <SDL3/SDL_main.h>
#include <bcrypt.h>
#include <deque>
#include <iomanip>
#include <limits>
#include <psapi.h>
#include <set>
#include <sstream>
#include <windows.h>

namespace ca {
namespace {
void check(bool ok) {
    if (!ok)
        throw std::runtime_error(SDL_GetError());
}

double timeNow() { return SDL_GetTicksNS() / 1e9; }

std::string sha256(const fs::path &file) {
    std::ifstream stream(file, std::ios::binary | std::ios::ate);
    const auto size = stream.tellg();
    if (size <= 0 || uint64_t(size) > std::numeric_limits<ULONG>::max())
        throw std::runtime_error("Cannot open video: " + file.filename().string());
    std::vector<unsigned char> bytes(static_cast<size_t>(size));
    stream.seekg(0);
    if (!stream.read(reinterpret_cast<char *>(bytes.data()), size))
        throw std::runtime_error("Cannot read video: " + file.filename().string());
    unsigned char hash[32]{};
    if (BCryptHash(BCRYPT_SHA256_ALG_HANDLE, nullptr, 0, bytes.data(), ULONG(bytes.size()), hash, 32))
        throw std::runtime_error("Cannot hash video");
    std::ostringstream hex;
    for (const auto byte : hash)
        hex << std::hex << std::setw(2) << std::setfill('0') << int(byte);
    return hex.str();
}

class Clips {
    const Encounter &encounter;
    const fs::path media;
    std::string activeId, warmId;
    std::unique_ptr<Movie> active, warm;

    std::unique_ptr<Movie> open(const std::string &id, const MovieEntry *entry) const {
        const auto &scene = encounter.scenes.at(id);
        const auto &clip = scene.image;
        const auto file = encounter.street ? media / "once" / (scene.mediaId + ".mkv")
                                           : media / ((entry ? entry->file : scene.mediaId) + ".mp4");
        if (sha256(file) != (entry ? entry->hash : clip.hash))
            throw std::runtime_error("Movie hash mismatch: " + id);
        auto movie = std::make_unique<Movie>(file, clip.frames, encounter.width, encounter.height,
                                             encounter.street ? AV_PIX_FMT_BGRA : AV_PIX_FMT_YUV420P);
        movie->at(clip.start);
        return movie;
    }

  public:
    int highCount = 0, evictions = 0;
    Clips(const Encounter &encounter, const fs::path &media) : encounter(encounter), media(media) {}
    int count() const { return int(bool(active)) + int(bool(warm)); }
    size_t payloadBytes() const {
        return (active ? active->payloadBytes() : 0) + (warm ? warm->payloadBytes() : 0);
    }
    void measure() { highCount = std::max(highCount, count()); }
    void reset() {
        evictions += count();
        active.reset();
        warm.reset();
        activeId.clear();
        warmId.clear();
    }
    bool select(const std::string &id, const MovieEntry *entry = nullptr) {
        const auto &key = entry ? entry->file : id;
        if (activeId == key)
            return true;
        const bool prepared = warmId == key;
        evictions += int(bool(active));
        active.reset();
        if (prepared)
            active = std::move(warm);
        else {
            evictions += int(bool(warm));
            warm.reset();
            active = open(id, entry);
        }
        activeId = key;
        warmId.clear();
        measure();
        return prepared;
    }
    void prepare(const std::string &id, const MovieEntry *entry = nullptr) {
        const auto &key = entry ? entry->file : id;
        if (id.empty() || id == "@complete" || key == activeId || key == warmId)
            return;
        evictions += int(bool(warm));
        warm.reset();
        warm = open(id, entry);
        warmId = key;
        measure();
    }
    Movie &current() const { return *active; }
    const std::string &fileId() const { return activeId; }
};

struct Stamp {
    uint64_t submitted = 0;
    int generation = -1, frame = -1;
    const Scene *scene = nullptr;
    SDL_FRect picture{};
};

struct VisualCue {
    Cue kind;
    Point point;
    double start;
    int tier = 0, scoreDelta = 0, sourceFrame = -1;
    const Scene *source = nullptr;
    bool weak = false;
    LinyuanImpact attack = LinyuanImpact::claw;
    std::string material;
    int swordSlot = 0;
    bool returned = false;
};

using Texture = std::unique_ptr<SDL_Texture, decltype(&SDL_DestroyTexture)>;

void uploadYuv(SDL_Texture *texture, const AVFrame *src) {
    check(SDL_UpdateYUVTexture(texture, nullptr, src->data[0], src->linesize[0], src->data[1],
                               src->linesize[1], src->data[2], src->linesize[2]));
}

std::string cueName(Cue c) {
    switch (c) {
    case Cue::hit:
        return "hit";
    case Cue::purify:
        return "purify";
    case Cue::intercept:
        return "intercept";
    case Cue::miss:
        return "miss";
    case Cue::hurt:
        return "hurt";
    case Cue::civilian:
        return "civilian";
    case Cue::reload:
        return "reload";
    case Cue::ready:
        return "ready";
    case Cue::empty:
        return "empty";
    case Cue::special:
        return "special";
    default:
        return "ignored";
    }
}

struct App {
    SDL_Window *window;
    SDL_Renderer *renderer;
    Encounter encounter;
    Match game;
    Clips media;
    Ink ink;
    Sound sound;
    ScoreAudio scoreAudio;
    ScoreAudio ambience;
    std::unique_ptr<SDL_AudioStream, decltype(&SDL_DestroyAudioStream)> speech{nullptr, SDL_DestroyAudioStream};
    fs::path audioFolder;
    std::string speechId, speechCaption;
    size_t voiceIndex = 0;
    std::set<std::string> playedVoiceCues;
    int speechPriority = -1;
    float speechGain = 1.f;
    double speechEnd = 0;
    Receiver ownReceiver;
    Receiver &receiver;
    GamepadController gamepad;
    bool gunMode = false;
    bool linyuan = false, newFeedback = false, reducedFlash = false, automated = false;
    bool shakeEnabled = true;
    SDL_FRect picture{};
    int lastWindowGeneration = -1, lastWindowBegin = -1, warningGeneration = -1;
    int armorFirstFrame = -1;
    int closedWindowGeneration = -1, retryNode = -1;
    int revealGeneration = -1;
    double revealAt = -1;
    std::set<std::string> seenEnemies;
    bool campaignFight = false, returnToMenu = false;
    int startingLives = 0, startingEnergy = 0, startingArrows = 8;
    double startingReload = 0;
    double menuSeconds = 0, defeatedAt = 0;
    Texture texture{nullptr, SDL_DestroyTexture}, streetTexture{nullptr, SDL_DestroyTexture};
    fs::path streetFile;
    std::unique_ptr<Movie> streetMovie;
    int streetFrame = -1;
    double actionRate = 1;
    double playStarted = 0;
    fs::path evidence;
    Json replayInputs = Json::array();
    size_t replayIndex = 0;
    bool replayRecorded = false;
    std::string scenario;
    bool capture, dev = false, running = true, holding = false, fullscreen = false;
    std::optional<FrameWriter> frameWriter;
    std::deque<Stamp> history;
    Stamp visible;
    const MovieEntry *pendingEntry = nullptr;
    Point cursor{-100, -100};
    std::vector<VisualCue> effects;
    std::array<std::optional<Point>, 8> spentSwords{};
    int nextSword = 0, warningToneGeneration = -1;
    double recallDuration = 0, caseGlintAt = -1;
    std::map<std::string, double> voiceCooldownUntil;
    int hurtVoiceIndex = 0;
    double visualTime = 0, visualTick = 0, previousTick = 0, begun = 0, pauseAt = 0, captureNext = 0,
           clickAt = 0, completedAt = 0, hitForSwitch = 0, feedbackForSubmit = 0;
    int videoGeneration = -1, frame = -1, captureFrame = 0, pressGeneration = -1, action = 0, switches = 0,
        rejected = 0, attempts = 0, titleResident = -1;
    int replayCut = -1, totalMoviesPeak = 0;
    size_t processPeak = 0, payloadPeak = 0;
    bool switchPending = false, prepared = false, attemptedImpact = false,
         effectFinishedDuringReload = false;
    Json trace = Json::array(), transitions = Json::array(), intervals = Json::array(),
         submits = Json::array(), samples = Json::array();
    std::vector<int> intervalFor;
    std::vector<size_t> unpresentedShots;

    App(SDL_Window *w, SDL_Renderer *r, const fs::path &assets, Encounter level, fs::path out, std::string test,
        bool record, Receiver *sharedReceiver = nullptr, bool linyuanMode = false, bool updatedFeedback = false,
        bool dimFlash = false, bool humanLog = false, bool specialAllowed = false)
        : window(w), renderer(r), encounter(std::move(level)), game(encounter), media(encounter, assets),
          ink(r), audioFolder(assets.parent_path() / "audio"),
          receiver(sharedReceiver ? *sharedReceiver : ownReceiver), gunMode(sharedReceiver != nullptr),
          linyuan(linyuanMode), newFeedback(updatedFeedback), reducedFlash(dimFlash),
          automated(!out.empty() && !humanLog), evidence(std::move(out)), scenario(std::move(test)),
          capture(record), intervalFor(encounter.nodes.size(), -1) {
        if (specialAllowed)
            game.allowSpecial = true;
        sound.limitToWallClock(linyuan);
        if (linyuan && scenario.starts_with("retry-wave-")) {
            for (int i = 0; i < int(encounter.nodes.size()); ++i)
                if (encounter.nodes[i].flinch != "elite_flinch" && scenario == "retry-wave-" + std::to_string(i + 1))
                    retryNode = i;
            if (retryNode < 0)
                throw std::runtime_error("Unknown ordinary or raft retry wave: " + scenario);
        }
        const auto ambientFile = audioFolder / "ambience" / (encounter.ambience + ".wav");
        if (linyuan && fs::is_regular_file(ambientFile)) {
            ambience.openLoop(sound.device(), ambientFile);
            ambience.volume(.23f, 0.f);
        }
        if (linyuan || encounter.selectableDifficulty) {
            const auto track = !linyuan ? "festival" : fs::is_regular_file(audioFolder / "music/battle.wav") ? "battle" : "";
            scoreAudio.open(sound.device(), audioFolder, true, track);
            if (linyuan)
                scoreAudio.volume(.72f, .80f);
        }
        if (!evidence.empty() && scenario.starts_with("cut-")) {
            size_t used = 0;
            replayCut = std::stoi(scenario.substr(4), &used);
            if (used + 4 != scenario.size() || replayCut < 0 ||
                replayCut >= encounter.scenes.at(encounter.first).impact)
                throw std::runtime_error("Requested replay cut outside the first target window");
        }
        texture.reset(SDL_CreateTexture(renderer,
                                        encounter.street ? SDL_PIXELFORMAT_BGRA32 : SDL_PIXELFORMAT_IYUV,
                                        SDL_TEXTUREACCESS_STREAMING, encounter.width, encounter.height));
        check(bool(texture));
        if (encounter.street) {
            streetFile = assets / "once/street.mp4";
            if (sha256(streetFile) != encounter.street->hash)
                throw std::runtime_error("Street movie hash mismatch");
            streetTexture.reset(SDL_CreateTexture(renderer, SDL_PIXELFORMAT_IYUV,
                                                  SDL_TEXTUREACCESS_STREAMING, encounter.width,
                                                  encounter.height));
            check(bool(streetTexture));
            check(SDL_SetTextureBlendMode(texture.get(), SDL_BLENDMODE_BLEND_PREMULTIPLIED));
            startStreet();
            streetMovie.reset(); // The title keeps only the uploaded first picture.
        }
        media.select(encounter.first);
        upload(0);
        media.reset();
        if (!evidence.empty()) {
            fs::create_directories(evidence);
            if (capture) {
                fs::create_directories(evidence / "frames");
                frameWriter.emplace();
            }
        }
    }

    void record(const std::string &name, int f, int gen, double when) {
        if (evidence.empty())
            return;
        trace.push_back({{"event", name},
                         {"time", when - begun},
                         {"monotonic_seconds", when},
                         {"attempt", attempts},
                         {"clip", game.scene ? game.scene->image.id : ""},
                         {"media", game.scene ? game.scene->mediaId : ""},
                         {"frame", f},
                         {"generation", gen},
                         {"street_frame", streetFrame},
                         {"visual_time", visualTime},
                         {"visible_effects", effects.size()},
                         {"node", game.progress},
                         {"hp", game.hp},
                         {"arrows", game.arrows},
                         {"lives", game.lives},
                         {"score", game.score},
                         {"combo", game.combo},
                         {"energy", game.energy},
                         {"intercepts", game.blocks}});
    }

    void restart(int energy = 0) {
        stopSpeech("restart");
        if (defeatedAt > 0) {
            menuSeconds += timeNow() - defeatedAt;
            defeatedAt = 0;
        }
        ++attempts;
        media.reset();
        game.start(campaignFight ? startingEnergy : energy);
        scoreAudio.rewind();
        if (campaignFight) {
            game.lives = attempts <= 1 ? startingLives : game.rules.lives;
            game.arrows = attempts <= 1 ? startingArrows : 8;
            game.reloadLeft = attempts <= 1 ? startingReload : 0.;
            if (attempts > 1)
                game.energy = 0;
        }
        history.clear();
        visible = {};
        pendingEntry = nullptr;
        effects.clear();
        seenEnemies.clear();
        playedVoiceCues.clear();
        spentSwords.fill(std::nullopt);
        nextSword = 0;
        recallDuration = game.reloadLeft;
        caseGlintAt = -1;
        for (int i = 0; i < 8 - game.arrows; ++i)
            spentSwords[i] = Point{330. + i * 79., 300. + (i % 3) * 44.};
        revealGeneration = -1;
        revealAt = -1;
        startStreet();
        visualTime = 0;
        visualTick = timeNow();
        playStarted = visualTick;
        std::fill(intervalFor.begin(), intervalFor.end(), -1);
        record("start", -1, game.generation, timeNow());
    }

    void goTitle() {
        stopSpeech("leave");
        if (campaignFight) {
            returnToMenu = true;
            running = false;
        }
        game.title();
        media.reset();
        history.clear();
        visible = {};
        pendingEntry = nullptr;
        effects.clear();
        streetMovie.reset();
        titleResident = media.count() + int(bool(streetMovie));
        sound.silenceClip();
        record("title", -1, game.generation, timeNow());
    }

    void pause() {
        if (game.screen != Screen::play)
            return;
        const double now = timeNow();
        game.paused = !game.paused;
        if (game.paused) {
            pauseAt = now;
            if (speech)
                SDL_UnbindAudioStream(speech.get());
        } else {
            menuSeconds += now - pauseAt;
            if (!speechId.empty())
                speechEnd += now - pauseAt;
            if (!game.pending.empty())
                game.frozenUntil += now - pauseAt;
            if (speech)
                SDL_BindAudioStream(sound.device(), speech.get());
        }
        record(game.paused ? "pause" : "resume", frame, game.generation, now);
    }

    void feedback(Cue c, Point point, double timestamp, int node = -1, int shown = -1, int points = 0) {
        if (c == Cue::none)
            return;
        const int activeNode = node >= 0 ? node
                               : (game.progress >= 0 && game.progress < int(encounter.nodes.size()))
                                   ? game.progress
                                   : -1;
        const Node *nodeSpec = activeNode >= 0 ? &encounter.nodes[activeNode] : nullptr;
        const std::string mediaId = game.scene ? game.scene->mediaId : "";
        const int tier = c == Cue::special ? 4
                         : c == Cue::hit     ? 1
                         : c == Cue::purify && nodeSpec &&
                                 (nodeSpec->tier > 0
                                      ? nodeSpec->tier >= 3
                                      : (nodeSpec->hp > 1 && (!linyuan || mediaId.find("pangolin") != std::string::npos)))
                             ? 3
                         : c == Cue::purify || c == Cue::intercept ? 2
                                                                   : 0;
        const std::string nodeMat = nodeSpec && !nodeSpec->material.empty()       ? nodeSpec->material
                                    : mediaId.find("bifang") != std::string::npos ? "feather"
                                    : mediaId.find("raft") != std::string::npos   ? "vine"
                                                                                  : "ceramic";
        const bool wing = nodeMat == "feather";
        const std::string sceneAttack = game.scene ? game.scene->attack : "";
        const bool blast = sceneAttack == "blast" ||
                           (sceneAttack.empty() && mediaId.find("pangolin") != std::string::npos);
        const bool collision = sceneAttack == "collision" ||
                               (sceneAttack.empty() &&
                                (wing || mediaId.find("raft") != std::string::npos ||
                                 mediaId.find("suanni_steps") != std::string::npos));
        const auto attack = blast       ? LinyuanImpact::blast
                            : collision ? LinyuanImpact::collision
                                        : LinyuanImpact::claw;
        const auto material = c == Cue::miss && newFeedback && game.scene
                                  ? encounter.materialAt(*game.scene, shown, point)
                              : c == Cue::intercept ? "crystal"
                                                    : nodeMat;
        const bool weak = (c == Cue::hit || c == Cue::purify) && game.lastWeakHit;
        int swordSlot = nextSword;
        const bool returned = linyuan && weak;
        if (linyuan && shown >= 0 &&
            (c == Cue::hit || c == Cue::purify || c == Cue::intercept || c == Cue::miss)) {
            for (int i = 0; i < 8 && spentSwords[swordSlot]; ++i)
                swordSlot = (swordSlot + 1) % 8;
            if (!returned)
                spentSwords[swordSlot] = point;
            nextSword = (swordSlot + 1) % 8;
        }
        if (c == Cue::reload) {
            recallDuration = game.reloadLeft;
        } else if (c == Cue::ready) {
            spentSwords.fill(std::nullopt);
            caseGlintAt = visualTime;
        } else {
            effects.push_back({c, point, visualTime, tier, points, shown, game.scene, weak, attack, material,
                               swordSlot, returned});
        }
        Feedback tone = Feedback::hit;
        if (c == Cue::civilian)
            tone = Feedback::civilian;
        else if (c == Cue::miss)
            tone = Feedback::miss;
        else if (c == Cue::hurt)
            tone = Feedback::hurt;
        else if (c == Cue::intercept || c == Cue::special || c == Cue::purify || c == Cue::ready)
            tone = Feedback::bonus;
        else if (c == Cue::empty || c == Cue::reload)
            tone = Feedback::reload;
        std::string sample = c == Cue::empty ? "ready" : cueName(c);
        if (newFeedback) {
            switch (c) {
            case Cue::hit:
                if (linyuan && weak)
                    scoreAudio.cue("canister");
                sample = wing ? "hit_wing" : "hit_ceramic";
                break;
            case Cue::purify:
                scoreAudio.cue(wing ? "hit_wing" : "hit_ceramic", 1.f, linyuan ? .85f : 1.f);
                if (game.lastWeakHit)
                    scoreAudio.cue("canister");
                sample = "kill";
                break;
            case Cue::hurt:
                sample = blast       ? "hurt_blast"
                         : collision ? "hurt_impact"
                                     : "hurt_claw";
                break;
            case Cue::empty:
                sample = "empty";
                break;
            case Cue::miss: {
                const bool marked =
                    material == "water" || material == "stone" || material == "earth" || material == "bamboo";
                sample = material == "metal" ? "miss_stone" : marked ? "miss_" + material : "miss";
                break;
            }
            default:
                break;
            }
        }
        const float gain = linyuan && newFeedback && c == Cue::purify ? .68f : 1.f;
        const float pitch = newFeedback && tier == 3 ? .76f : 1.f;
        const int recalled = linyuan && c == Cue::reload ? 8 - game.arrows : 8;
        if (!scoreAudio.cue(sample, pitch, gain, recalled))
            sound.cue(tone);
        if (linyuan && newFeedback && !game.paused) {
            if (c == Cue::empty)
                triggerOptionalVoice("qingping/reload", "青萍  剑用完了，收剑！", 1, 8.);
            else if (c == Cue::civilian)
                triggerOptionalVoice("qingping/protect", "青萍  别打人！", 2, 3.);
            else if (c == Cue::hurt) {
                static const char *const lines[] = {"qingping/hurt_1", "qingping/hurt_2", "qingping/hurt_3"};
                static const char *const subs[] = {"青萍  陆沉！", "青萍  还撑得住吗？", "青萍  小心！"};
                const int idx = hurtVoiceIndex++ % 3;
                triggerOptionalVoice(lines[idx], subs[idx], 1, 10.);
            }
        }
        if (!evidence.empty() && !linyuan)
            feedbackForSubmit = timestamp;
    }

    void triggerOptionalVoice(const std::string &voice, const std::string &caption, int priority,
                              double cooldownSeconds) {
        const double now = timeNow();
        if (voiceCooldownUntil[voice] > now || (!speechId.empty() && speechPriority > priority))
            return;
        const auto path = (audioFolder / "voice" / (voice + ".wav")).u8string();
        if (!fs::is_regular_file(audioFolder / "voice" / (voice + ".wav")))
            return;
        SDL_AudioSpec spec{};
        Uint8 *raw = nullptr;
        Uint32 bytes = 0;
        if (!SDL_LoadWAV(reinterpret_cast<const char *>(path.c_str()), &spec, &raw, &bytes))
            return;
        std::unique_ptr<Uint8, decltype(&SDL_free)> owner(raw, SDL_free);
        stopSpeech("preempted");
        if (sound.device()) {
            speech.reset(SDL_CreateAudioStream(&spec, &spec));
            if (!speech || !SDL_BindAudioStream(sound.device(), speech.get()) ||
                !SDL_SetAudioStreamGain(speech.get(), speechGain) ||
                !SDL_PutAudioStreamData(speech.get(), raw, bytes) || !SDL_FlushAudioStream(speech.get()))
                return;
        }
        speechPriority = priority;
        speechId = voice;
        speechCaption = caption;
        const double duration = double(bytes) / (spec.freq * SDL_AUDIO_FRAMESIZE(spec));
        speechEnd = now + duration;
        voiceCooldownUntil[voice] = now + cooldownSeconds;
    }

    void shot(Point point, uint64_t ns, bool thunder) {
        if (linyuan && !game.allowSpecial && thunder)
            return;
        auto f = std::find_if(history.rbegin(), history.rend(),
                              [ns](const Stamp &s) { return s.submitted <= ns; });
        if (f == history.rend() || ns - f->submitted > 300000000 || f->generation != game.generation)
            return;
        const Point screenPoint = point;
        if (f->picture.w > 0 && f->picture.h > 0)
            point = {(point.x - f->picture.x) * encounter.width / f->picture.w,
                     (point.y - f->picture.y) * encounter.height / f->picture.h};
        const double time = ns / 1e9;
        const auto *w = f->scene->window(f->frame);
        const int wasNode = game.progress;
        const int before = game.shots;
        const int priorPoints = game.score;
        Cue cue = game.input(point, f->generation, f->frame, thunder, timeNow());
        if (game.shots > before)
            scoreAudio.cue("shot", 1.f, linyuan && newFeedback ? .78f : 1.f);
        if (game.shots > before && w && (w->kind == Kind::target || (linyuan && w->kind == Kind::projectile)) &&
            wasNode < int(intervalFor.size()) &&
            intervalFor[wasNode] != -1) {
            auto &sample = intervals.at(intervalFor[wasNode]);
            if (sample["t_input"].is_null()) {
                sample["t_input"] = time - begun;
                sample["reaction_ms"] = 1000 * (time - begun - sample["t_open"].get<double>());
            }
        }
        if (cue == Cue::none)
            ++rejected;
        if (!game.pending.empty() && cue != Cue::none) {
            hitForSwitch = time;
            pendingEntry = encounter.entrance(*f->scene, game.pending, f->frame);
        }
        if (game.progress > wasNode && game.progress < int(encounter.nodes.size())) {
            intervalFor[game.progress] = int(intervals.size());
            intervals.push_back({{"from", encounter.nodes[wasNode].id},
                                 {"to", encounter.nodes[game.progress].id},
                                 {"t_hit", time - begun},
                                 {"t_open", nullptr},
                                 {"t_input", nullptr},
                                 {"hit_frame", f->frame}});
        }
        const Point location = thunder ? f->scene->center(f->frame) : point;
        feedback(cue, location, time, wasNode, f->frame, game.score - priorPoints);
        record(thunder ? "thunder_" + cueName(cue) : "shot_" + cueName(cue), f->frame, f->generation, time);
        if (!evidence.empty()) {
            auto &event = trace.back();
            event["input_x"] = point.x;
            event["input_y"] = point.y;
            event["screen_x"] = screenPoint.x;
            event["screen_y"] = screenPoint.y;
            event["weak"] = game.lastWeakHit;
            if (game.shots > before)
                unpresentedShots.push_back(trace.size() - 1);
        }
    }

    void setGunMode(bool enable) {
        if (enable) {
            gunMode = receiver.open();
            if (!gunMode)
                SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "TVGun", "无法打开 TVGun 接收端口。",
                                         window);
        } else {
            receiver.close();
            gunMode = false;
        }
    }

    void remote(RemoteAction action, Point point) {
        Point target{point.x * encounter.width / 1920., point.y * encounter.height / 1080.};
        switch (action) {
        case RemoteAction::aim:
            cursor = target;
            break;
        case RemoteAction::lost:
        case RemoteAction::exit:
            if (game.screen == Screen::play && !game.paused)
                pause();
            cursor = {-100, -100};
            break;
        case RemoteAction::start:
            if (game.screen != Screen::play)
                restart();
            else if (game.paused && receiver.hasLock())
                pause();
            break;
        case RemoteAction::reload:
            reload();
            break;
        case RemoteAction::shoot:
        case RemoteAction::special:
            if (target.x < 0 || target.x >= encounter.width || target.y < 0 ||
                target.y >= encounter.height) {
                if (action == RemoteAction::shoot)
                    reload();
            } else {
                shot(target, SDL_GetTicksNS(), action == RemoteAction::special);
            }
            break;
        }
    }

    void events() {
        if (gunMode)
            receiver.poll(SDL_GetTicks(), [this](RemoteAction action, Point p) { remote(action, p); });
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            gamepad.poll(
                event, cursor,
                [&](Point p, uint64_t ns) {
                    if (game.screen != Screen::play)
                        restart();
                    else if (game.paused)
                        pause();
                    else
                        shot(p, ns, false);
                },
                [&] { reload(); },
                [&] {
                    if (game.screen == Screen::play && !game.paused)
                        shot(cursor, SDL_GetTicksNS(), true);
                },
                [&] {
                    if (game.screen == Screen::play)
                        pause();
                    else if (game.screen != Screen::play)
                        restart();
                });
            const auto type = event.type;
            if (type == SDL_EVENT_QUIT)
                running = false;
            if (type == SDL_EVENT_WINDOW_FOCUS_LOST && !automated && !game.paused)
                pause();
            if (type == SDL_EVENT_KEY_DOWN && !event.key.repeat) {
                switch (event.key.key) {
                case SDLK_F2:
                    if (!campaignFight)
                        setGunMode(!gunMode);
                    break;
                case SDLK_1:
                case SDLK_2:
                case SDLK_3:
                    if (encounter.selectableDifficulty && game.screen == Screen::title)
                        game.rules = difficulty(event.key.key == SDLK_1   ? "easy"
                                                : event.key.key == SDLK_2 ? "normal"
                                                                          : "hard");
                    break;
                case SDLK_ESCAPE:
                    if (game.screen == Screen::play)
                        pause();
                    else if (game.screen == Screen::title)
                        running = false;
                    else
                        goTitle();
                    break;
                case SDLK_RETURN:
                    if (game.screen != Screen::play)
                        restart(scenario.starts_with("thunder") ? game.rules.charge : 0);
                    else if (game.paused)
                        pause();
                    break;
                case SDLK_R:
                    reload();
                    break;
                case SDLK_SPACE:
                    shot(cursor, event.key.timestamp, true);
                    break;
                case SDLK_F3:
                    dev = !dev;
                    break;
                case SDLK_F11:
                    fullscreen = !fullscreen;
                    SDL_SetWindowFullscreen(window, fullscreen);
                    break;
                default:
                    break;
                }
            }
            if (type == SDL_EVENT_MOUSE_MOTION || type == SDL_EVENT_MOUSE_BUTTON_DOWN) {
                SDL_ConvertEventToRenderCoordinates(renderer, &event);
                if (type == SDL_EVENT_MOUSE_MOTION) {
                    cursor = {event.motion.x, event.motion.y};
                    continue;
                }
                cursor = {event.button.x, event.button.y};
                if (event.button.button == SDL_BUTTON_LEFT && game.screen != Screen::play) {
                    if (encounter.selectableDifficulty && game.screen == Screen::title && cursor.y >= 376 &&
                        cursor.y <= 408) {
                        if (cursor.x >= 72 && cursor.x <= 152)
                            game.rules = difficulty("easy");
                        else if (cursor.x >= 162 && cursor.x <= 242)
                            game.rules = difficulty("normal");
                        else if (cursor.x >= 252 && cursor.x <= 332)
                            game.rules = difficulty("hard");
                    }
                    if (cursor.x >= 68 && cursor.x <= 388 && cursor.y >= 401 && cursor.y <= 484)
                        restart();
                    else if (linyuan && game.screen == Screen::failed && cursor.x >= 68 && cursor.x <= 388 &&
                             cursor.y >= 491 && cursor.y <= 540)
                        running = false;
                    continue;
                }
                if (event.button.button == SDL_BUTTON_LEFT && game.paused) {
                    if (cursor.x >= 68 && cursor.x <= 388 && cursor.y >= 401 && cursor.y <= 484)
                        pause();
                    else if (cursor.x >= 68 && cursor.x <= 388 && cursor.y >= 491 && cursor.y <= 540)
                        goTitle();
                    continue;
                }
                if (event.button.button == SDL_BUTTON_RIGHT)
                    reload();
                else if (event.button.button == SDL_BUTTON_LEFT ||
                         event.button.button == SDL_BUTTON_MIDDLE) {
                    if (cursor.x >= 0 && cursor.x < encounter.width && cursor.y >= 0 &&
                        cursor.y < encounter.height)
                        shot(cursor, event.button.timestamp, event.button.button == SDL_BUTTON_MIDDLE);
                }
            }
        }
        gamepad.updateAim(cursor, encounter.width, encounter.height, [&](Point p, uint64_t ns) {
            if (game.screen == Screen::play && !game.paused)
                shot(p, ns, false);
        });
    }

    void reload() {
        const double time = timeNow();
        const Cue cue = game.reload(time);
        feedback(cue, cursor, time);
        if (cue == Cue::reload) {
            record("reload_begin", frame, game.generation, time);
            if (!evidence.empty() && linyuan)
                trace.back()["duration_seconds"] = game.reloadLeft;
        }
    }

    void upload(int f) {
        const auto *src = media.current().at(f);
        if (encounter.street)
            check(SDL_UpdateTexture(texture.get(), nullptr, src->data[0], src->linesize[0]));
        else
            uploadYuv(texture.get(), src);
    }

    void startStreet() {
        if (!encounter.street)
            return;
        if (!streetMovie)
            streetMovie = std::make_unique<Movie>(streetFile, encounter.street->frames, encounter.width,
                                                  encounter.height);
        streetFrame = 0;
        uploadYuv(streetTexture.get(), streetMovie->at(0));
    }

    void syncStreet() {
        if (!streetMovie || game.screen == Screen::title || game.paused)
            return;
        const int last = encounter.street->frames - 1;
        const int next = std::min({int(visualTime * 24), streetFrame + 1, last});
        if (next > streetFrame) {
            uploadYuv(streetTexture.get(), streetMovie->at(next));
            streetFrame = next;
        }
        if (streetFrame == last)
            streetMovie.reset(); // Hold the texture across every later hit, loop and recovery.
    }

    void sync(double time) {
        if (game.screen != Screen::play) {
            if (!holding) {
                holding = true;
                sound.silenceClip();
            }
            return;
        }
        if (videoGeneration != game.generation) {
            voiceIndex = 0;
            prepared = media.select(game.scene->image.id, pendingEntry);
            pendingEntry = nullptr;
            frame = game.scene->image.start;
            upload(frame);
            actionRate = game.playbackRate(frame);
            sound.begin(media.current(), frame, actionRate, timeNow());
            videoGeneration = game.generation;
            holding = false;
            switchPending = true;
            return;
        }
        if (game.paused || !game.pending.empty() || game.isFrozen()) {
            if (!holding) {
                sound.silenceClip();
                holding = true;
            }
            return;
        }
        if (holding || actionRate != game.playbackRate(frame)) {
            actionRate = game.playbackRate(frame);
            sound.begin(media.current(), frame, actionRate, time);
            holding = false;
        }
        int ceiling = game.scene->end - 1;
        if (game.scene->holdFrame >= 0 && game.pending.empty())
            ceiling = std::min(ceiling, game.scene->holdFrame);
        const int desired = std::min({sound.localFrame(time), ceiling, frame + 1});
        if (desired > frame) {
            frame = desired;
            upload(frame);
        }
        if (game.scene->holdFrame >= 0 && frame == game.scene->holdFrame && game.pending.empty() && !holding) {
            sound.silenceClip();
            holding = true;
        }
    }

    void stopSpeech(const char *reason) {
        if (speechId.empty())
            return;
        record("voice_end", frame, game.generation, timeNow());
        if (!evidence.empty()) {
            trace.back()["voice"] = speechId;
            trace.back()["reason"] = reason;
        }
        speechId.clear();
        speechCaption.clear();
        speech.reset();
    }

    void combatSpeech() {
        if (!linyuan || game.screen != Screen::play || !game.scene || game.paused)
            return;
        if (!speechId.empty() && timeNow() >= speechEnd)
            stopSpeech("finished");
        if (!game.pending.empty())
            return;
        const auto &cues = game.scene->voiceCues;
        while (voiceIndex < cues.size() && frame >= cues[voiceIndex].frame) {
            const auto &cue = cues[voiceIndex++];
            if (playedVoiceCues.contains(cue.voice) || (!speechId.empty() && speechPriority > cue.priority))
                continue;
            const auto path = (audioFolder / "voice" / (cue.voice + ".wav")).u8string();
            SDL_AudioSpec spec{};
            Uint8 *raw = nullptr;
            Uint32 bytes = 0;
            if (!SDL_LoadWAV(reinterpret_cast<const char *>(path.c_str()), &spec, &raw, &bytes))
                throw std::runtime_error("Missing combat voice: " + cue.voice);
            std::unique_ptr<Uint8, decltype(&SDL_free)> owner(raw, SDL_free);
            stopSpeech("preempted");
            if (sound.device()) {
                speech.reset(SDL_CreateAudioStream(&spec, &spec));
                if (!speech || !SDL_BindAudioStream(sound.device(), speech.get()) ||
                    !SDL_SetAudioStreamGain(speech.get(), speechGain) ||
                    !SDL_PutAudioStreamData(speech.get(), raw, bytes) || !SDL_FlushAudioStream(speech.get()))
                    throw std::runtime_error(SDL_GetError());
            }
            speechPriority = cue.priority;
            playedVoiceCues.insert(cue.voice);
            speechId = cue.voice;
            speechCaption = cue.subtitle;
            const double duration = double(bytes) / (spec.freq * SDL_AUDIO_FRAMESIZE(spec));
            speechEnd = timeNow() + duration;
            record("voice_" + cue.voice, frame, game.generation, timeNow());
            if (!evidence.empty())
                trace.back()["duration_seconds"] = duration;
        }
    }

    void warmNext() {
        if (game.screen != Screen::play || game.paused)
            return;
        if (!game.pending.empty()) {
            media.prepare(game.pending, pendingEntry);
            return;
        }
        if (const auto *w = game.scene->window(frame); w && game.active(w)) {
            const auto &node = encounter.nodes[w->node];
            const auto &dest = w->kind == Kind::target && game.hp > 1 && node.weakDamage == 1 ? node.flinch : w->onHit;
            media.prepare(dest, encounter.entrance(*game.scene, dest, frame));
            return;
        }
        for (const auto &next : game.scene->windows)
            if (next.begin > frame && game.active(&next)) {
                const auto &node = encounter.nodes[next.node];
                const auto &dest = next.kind == Kind::target && game.hp > 1 && node.weakDamage == 1 ? node.flinch : next.onHit;
                media.prepare(dest, encounter.entrance(*game.scene, dest, next.begin));
                return;
            }
        media.prepare(game.scene->image.next);
    }

    void drawTargetSignals(const Window &target) {
        const Scene &scene = *game.scene;
        const auto box = linyuanBounds(scene.image.masks.at(frame), picture);
        if (box.w <= 0)
            return;
        Point center{box.x + box.w / 2, box.y + box.h / 2};
        if (target.kind == Kind::target && revealGeneration != game.generation) {
            revealGeneration = game.generation;
            std::string species = scene.mediaId;
            if (species.starts_with("c1_w_")) {
                species.erase(0, 5);
                species = species.substr(0, species.find('_'));
            }
            const bool first = seenEnemies.insert(species).second;
            revealAt = !scene.holdSeconds && (first || center.x < 384 || center.x > 896) ? visualTime : -1;
            if (revealAt >= 0)
                scoreAudio.cue("reveal");
        }
        const double age = revealAt < 0 ? 1. : visualTime - revealAt;
        if (target.kind == Kind::target) {
            if (age < .35) {
                const SDL_Color cyan{77, 255, 210, Uint8(205 * (1 - age / .35))};
                ink.ring(center, int(3 + std::min(1., age / .12) * 37), cyan);
                linyuanOutlinedBrackets(ink, box, float(3 + std::max(0., 1 - age / .12) * 12), cyan);
            } else {
                linyuanOutlinedBrackets(ink, box, 4.f, {92, 255, 218, 175});
            }
        }
        double urgency = 0.;
        if (scene.impact > frame && scene.warning >= 0 && frame >= scene.warning) {
            const double left = double(scene.impact - frame) / (scene.impact - scene.warning);
            urgency = 1. - left;
            if (target.kind == Kind::projectile) {
                const float x = float(center.x), y = float(center.y), r = 16.f;
                for (int side : {-1, 1})
                    for (int top : {-1, 1})
                        linyuanOutlinedStroke(ink, x + r * side, y, x, y + r * top, 2.8f, {255, 112, 67, 245});
            } else
                linyuanOutlinedBrackets(ink, box, float(3 + left * 10), {255, 112, 67, 235});
            linyuanCountdown(ink, center, std::max(24.f, std::min(50.f, box.h * .65f)), left);
        }
        auto markWeak = [&](Point spot, double height) {
            const float radius = float(std::clamp(height * .58, 18., 40.));
            drawLinyuanTargetLock(ink, spot, radius, visualTime, age, urgency,
                                  target.kind == Kind::projectile);
        };
        if (target.weak)
            markWeak(center, box.h);
        else if (!scene.weakSpots.empty())
            for (const auto &spot : scene.weakSpots.at(frame))
                markWeak({picture.x + spot.center.x * picture.w / encounter.width,
                          picture.y + spot.center.y * picture.h / encounter.height},
                         spot.height * picture.h / encounter.height);
    }

    double dangerProgress() const {
        if (!game.interactive() || !game.scene || game.scene->warning < 0 || frame < game.scene->warning ||
            frame >= game.scene->impact)
            return -1;
        const double seconds = (game.scene->impact - frame) / (24. * game.playbackRate(frame));
        return seconds > .5 ? -1 : 1. - 2. * seconds;
    }

    void drawHud() {
        const float right = float(encounter.width) - 38;
        const double danger = dangerProgress();
        if (linyuan && newFeedback && danger >= 0) {
            for (const auto &track : game.scene->threatTracks) {
                const auto found = track.find(frame);
                if (found == track.end())
                    continue; // The second eye or attacker can move out of shot.
                const Point p = found->second;
                threatGlow(ink,
                           {picture.x + p.x * picture.w / encounter.width,
                            picture.y + p.y * picture.h / encounter.height},
                           danger, reducedFlash);
            }
        }
        if (!speechCaption.empty()) {
            ink.box(160.f, encounter.height - 86.f, encounter.width - 320.f, 44.f, {9, 12, 20, 196});
            ink.text(encounter.width / 2.f, encounter.height - 76.f, 22, speechCaption, ivory, true);
        }
        ink.box(22, 16, 280, 58, {13, 19, 26, 220});
        ink.text(36, 23, 15, encounter.location, ivory);
        for (int n = 0; n < game.rules.lives; ++n)
            ink.star({44. + (game.rules.lives > 3 ? 16 : 21) * n, 57}, 6,
                     n < game.lives ? gold : SDL_Color{111, 91, 82, 245});
        for (int n = 0; n < 8; ++n)
            ink.box(134.f + n * 13.f, 52, 8, 10, n < game.arrows ? ivory : SDL_Color{104, 102, 95, 220});
        ink.text(244, 46, 14,
                 game.reloadLeft > 0 ? (linyuan ? "收剑中" : "换匣中") : (linyuan ? "飞剑" : "符箭"), gold);
        ink.box(right - 276, 16, 276, 58, {13, 19, 26, 220});
        ink.text(right - 258, 23, 16, progressLabel(), ivory);
        ink.text(right - 102, 23, 16, std::to_string(game.score) + " 分", ivory);
        if (!linyuan || game.allowSpecial) {
            ink.box(right - 258, 55, 118, 5, {85, 75, 65, 235});
            ink.box(right - 258, 55, 118.f * game.energy / game.rules.charge, 5, gold);
            ink.text(right - 130, 46, 15,
                     game.energy == game.rules.charge ? (linyuan ? "空格/中键 归宗" : "空格 雷符")
                                                      : (linyuan ? "剑意" : "雷符"),
                     gold);
        }
        if (linyuan && !game.arrows && !game.reloadLeft) {
            const float ry = game.allowSpecial ? 80.f : 50.f;
            ink.box(right - 208, ry, 208, 32, {13, 19, 26, 220});
            ink.box(right - 208, ry, 3, 32, gold);
            ink.text(right - 104, ry + 5, 16, "右键或 R 收剑", gold, true);
        }

        if (game.progress < int(encounter.nodes.size())) {
            const Window *target = game.scene->window(frame);
            std::string help = encounter.nodes[game.progress].label;
            if (newFeedback && game.interactive() && game.active(target))
                drawTargetSignals(*target);
            else if (!newFeedback && game.active(target) && game.scene->impact > frame && frame >= game.scene->warning) {
                const Point p = game.scene->center(frame);
                if (p.x >= 0)
                    ink.ring(
                        p, (target->kind == Kind::projectile ? 17 : 20) + (game.scene->impact - frame) / 2,
                        {250, 156, 117, 148});
            }
            if (game.interactive() && game.active(target)) {
                if (target->kind == Kind::projectile)
                    help = linyuan ? "拦截飞针" : "拦截青火球";
                else if (target->kind == Kind::civilian)
                    help = linyuan ? "货郎经过  ·  莫出剑" : "百姓经过  ·  收弩";
                else if (linyuan && encounter.nodes[game.progress].weakDamage > 1)
                    help = "白甲 " + std::to_string(game.hp) + " 剑  ·  肩罐 1 剑";
                else if (encounter.nodes[game.progress].hp > 1)
                    help += "  ·  还需 " + std::to_string(game.hp) + " 次";
                ink.box(encounter.width / 2.f - 185, 18.f, 370, 38, {13, 19, 26, 208});
                ink.box(encounter.width / 2.f - 185, 18.f, 370, 2, {204, 158, 86, 180});
                ink.text(encounter.width / 2.f, 26.f, 18, help, gold, true);
            }
        }
        for (const auto &effect : effects)
            drawEffect(effect, visualTime - effect.start);
        if (linyuan && newFeedback) {
            if (game.reloadLeft > 0 && recallDuration > 0) {
                const double fraction = std::clamp(1 - game.reloadLeft / recallDuration, 0., 1.);
                const int count = int(std::count_if(spentSwords.begin(), spentSwords.end(),
                                                    [](const auto &s) { return s.has_value(); }));
                int sequence = 0;
                for (int slot = 0; slot < 8; ++slot) {
                    if (!spentSwords[slot])
                        continue;
                    const auto from = *spentSwords[slot];
                    const double stagger = count < 2 ? 0. : .35 * sequence++ / (count - 1);
                    returnSword(ink, from, slot, (fraction - stagger) / (count < 2 ? 1. : .65), reducedFlash);
                }
            }
            if (caseGlintAt >= 0)
                caseGlint(ink, caseMouth(7), visualTime - caseGlintAt, reducedFlash);
        }
        if (cursor.x >= 0 && cursor.x < encounter.width && cursor.y >= 0 && cursor.y < encounter.height) {
            const float x = float(cursor.x), y = float(cursor.y);
            if (newFeedback) {
                const auto *win = game.scene->window(frame);
                const Point source{(cursor.x - picture.x) * encounter.width / picture.w,
                                   (cursor.y - picture.y) * encounter.height / picture.h};
                const bool pointed = game.interactive() && game.active(win) &&
                                     game.scene->aimCovers(frame, source, game.rules.aimRadius);
                drawLinyuanReticle(ink, cursor, game.arrows, game.reloadLeft > 0, pointed,
                                   pointed && (win->weak || game.scene->weakAt(frame, source)),
                                   pointed && win->kind == Kind::civilian,
                                   linyuan && game.allowSpecial && game.energy == game.rules.charge);
            } else {
                ink.ring(cursor, 8, {247, 230, 189, 198});
                ink.line(x - 13, y, x - 5, y, ivory);
                ink.line(x + 5, y, x + 13, y, ivory);
                ink.line(x, y - 13, x, y - 5, ivory);
                ink.line(x, y + 5, x, y + 13, ivory);
            }
        }
        if (dev) {
            if (game.scene->window(frame)) {
                for (const auto &s : game.scene->image.masks.at(frame))
                    ink.box(2.f * s.x0, 2.f * s.y, 2.f * (s.x1 - s.x0), 2.f, {66, 240, 203, 104});
            }
            ink.text(32, 109, 18, game.scene->image.id + " #" + std::to_string(frame), ivory);
        }
    }

    void drawEffect(const VisualCue &cue, double age) {
        if (newFeedback) {
            const Point screen{picture.x + cue.point.x * picture.w / encounter.width,
                               picture.y + cue.point.y * picture.h / encounter.height};
            const bool pulse = age < .105 && cue.source == game.scene;
            if (cue.tier && pulse && cue.source && cue.sourceFrame >= 0 &&
                cue.sourceFrame < int(cue.source->image.masks.size())) {
                const auto &outline = cue.source->image.masks[cue.sourceFrame];
                std::vector<SDL_FRect> stripes;
                stripes.reserve(outline.size());
                const float sx = 2.f * picture.w / encounter.width, sy = 2.f * picture.h / encounter.height;
                for (const auto &s : outline)
                    stripes.push_back({picture.x + s.x0 * sx, picture.y + s.y * sy, (s.x1 - s.x0) * sx, sy});
                const double decay = std::max(0., 1. - age / .105);
                SDL_SetRenderDrawColor(renderer, 255, 246, 211,
                                       Uint8((reducedFlash    ? 38
                                              : cue.tier == 3 ? 145
                                                              : 100) *
                                             decay));
                if (!stripes.empty())
                    SDL_RenderFillRects(renderer, stripes.data(), int(stripes.size()));
            }
            drawLinyuanEffect(ink, cue.kind, screen, age, reducedFlash, cue.tier, cue.weak, cue.attack,
                              cue.scoreDelta, cue.material, game.lives, cue.swordSlot, cue.returned);
            return;
        }
        const Cue effect = cue.kind;
        const Point &effectPoint = cue.point;
        const auto fade = Uint8(210 * (1 - age / .45));
        if (effect == Cue::hurt || effect == Cue::civilian) {
            ink.box(0, 0, float(encounter.width), 13, {227, 41, 29, fade});
            ink.box(0, encounter.height - 13.f, float(encounter.width), 13, {227, 41, 29, fade});
            ink.text(encounter.width / 2.f, 104, 28, effect == Cue::civilian ? "误伤百姓" : "受击",
                     {red.r, red.g, red.b, fade}, true);
        } else if (effect == Cue::empty) {
            ink.text(encounter.width / 2.f, 104, 24, "符匣已空  ·  右键换匣",
                     {gold.r, gold.g, gold.b, fade}, true);
        } else if (effect == Cue::hit || effect == Cue::purify || effect == Cue::intercept ||
                   effect == Cue::special || effect == Cue::miss) {
            const bool cyan = effect == Cue::intercept;
            const SDL_Color glow = cyan ? SDL_Color{122, 255, 234, fade} : SDL_Color{253, 206, 107, fade};
            const int radius = int(12 + 86 * age);
            ink.ring(effectPoint, radius, glow);
            if (effect != Cue::miss)
                for (int n = 0; n < 16; ++n) {
                    const double theta = n * .3926990817;
                    const double dist = radius * (1.1 + (n % 3) * .25);
                    ink.box(float(effectPoint.x + std::cos(theta) * dist),
                            float(effectPoint.y + std::sin(theta) * dist), 3, 3, glow);
                }
            if (effect == Cue::special) {
                ink.line(float(effectPoint.x + 72), 0, float(effectPoint.x - 20), float(effectPoint.y - 80),
                         glow);
                ink.line(float(effectPoint.x - 20), float(effectPoint.y - 80), float(effectPoint.x),
                         float(effectPoint.y), {ivory.r, ivory.g, ivory.b, fade});
            }
        }
    }

    std::string progressLabel() const {
        return encounter.progressPrefix + std::to_string(game.progress) + " / " +
               std::to_string(encounter.nodes.size());
    }

    void drawMenu() {
        auto screen = game.screen;
        ink.box(0, 0, float(encounter.width), float(encounter.height), {7, 11, 21, 124});
        ink.box(47, 137, 542, game.paused ? 430.f : 391.f, {12, 18, 29, 225});
        ink.box(70, 182, 45, 2, gold);
        ink.text(130, 169, 18, encounter.location, gold);
        std::string title = screen == Screen::title    ? encounter.title
                            : screen == Screen::failed ? (linyuan ? "剑穗已尽" : "灯火未平")
                                                       : encounter.cleared;
        if (game.paused)
            title = linyuan ? "暂停" : "巡街暂停";
        ink.text(68, 215, 59, title, ivory);
        std::string detail = screen == Screen::title
                                 ? encounter.briefing
                                 : progressLabel() + "     得分 " + std::to_string(game.score);
        if (game.paused)
            detail = "恢复后从当前镜头继续。";
        ink.text(72, 313, 21, detail, ivory);
        ink.text(72, 360, 17, linyuan ? "左键出剑  /  右键或 R 收剑" : "左键施符  /  右键换匣  /  空格雷符",
                 gold);
        if (encounter.selectableDifficulty && screen == Screen::title) {
            const std::pair<const char *, const char *> opts[] = {{"easy", "1 简单"}, {"normal", "2 普通"}, {"hard", "3 困难"}};
            for (int k = 0; k < 3; ++k) {
                const float bx = 72.f + k * 90.f;
                const bool active = game.rules.id == opts[k].first;
                ink.box(bx, 380, 82, 26, active ? gold : SDL_Color{28, 36, 46, 220});
                ink.text(bx + 41, 384, 15, opts[k].second, active ? SDL_Color{20, 22, 24, 255} : ivory, true);
            }
        }
        ink.box(68, 414, 320, 54, {212, 161, 81, 245});
        ink.text(228, 426, 24,
                 linyuan                   ? (screen == Screen::failed ? "续关" : "继续")
                 : game.paused             ? "继续巡街"
                 : screen == Screen::title ? "开始巡街"
                                           : "重新巡街",
                 {25, 22, 20, 255}, true);
        if (game.paused || (linyuan && screen == Screen::failed))
            ink.text(228, 502, 18, linyuan ? "结束" : "返回标题", ivory, true);
    }

    void saveFrame(const fs::path &path) {
        SDL_Surface *surface = SDL_RenderReadPixels(renderer, nullptr);
        if (!surface)
            throw std::runtime_error("Cannot read back capture");
        const auto file = path.u8string();
        const bool ok = SDL_SaveBMP(surface, reinterpret_cast<const char *>(file.c_str()));
        SDL_DestroySurface(surface);
        check(ok);
    }

    void render(double now) {
        SDL_SetRenderDrawColor(renderer, 9, 13, 21, 255);
        SDL_RenderClear(renderer);
        picture = {0, 0, float(encounter.width), float(encounter.height)};
        if (newFeedback && shakeEnabled && !effects.empty() && game.screen == Screen::play) {
            const auto &last = effects.back();
            const double amplitude = last.kind == Cue::hurt                                 ? 14.
                                     : linyuan && last.weak                                 ? 6.
                                     : last.tier == 3                                       ? 8.
                                     : last.kind == Cue::purify                             ? 4.
                                     : last.kind == Cue::hit || last.kind == Cue::intercept ? 3.
                                                                                            : 0.;
            const double elapsed = visualTime - last.start;
            const double strength =
                amplitude * std::max(0., 1. - elapsed / (last.kind == Cue::hurt ? .3 : .12));
            if (strength > 0) {
                picture.x = float(-strength + strength * std::cos(elapsed * 145.));
                picture.y = float(-strength + strength * std::sin(elapsed * 101.));
                picture.w += float(strength * 2);
                picture.h += float(strength * 2);
            }
        }
        if (streetTexture)
            check(SDL_RenderTexture(renderer, streetTexture.get(), nullptr, &picture));
        check(SDL_RenderTexture(renderer, texture.get(), nullptr, &picture));
        if (gunMode)
            drawGunBorder(ink);
        if (game.screen == Screen::play && frame >= 0 && game.scene)
            drawHud();
        if (newFeedback && game.screen == Screen::failed && !effects.empty() && effects.back().kind == Cue::hurt)
            drawEffect(effects.back(), visualTime - effects.back().start);
        if (game.screen != Screen::play || game.paused)
            drawMenu();

        if (!evidence.empty() && (automated || capture)) {
            if (!attempts && captureFrame == 0 && !fs::exists(evidence / "title.bmp"))
                saveFrame(evidence / "title.bmp");
            if (game.screen == Screen::complete && !fs::exists(evidence / "completed.bmp"))
                saveFrame(evidence / "completed.bmp");
            if (capture && now >= captureNext) {
                std::ostringstream name;
                name << std::setw(5) << std::setfill('0') << captureFrame << ".bmp";
                if (frameWriter->sample(renderer, evidence / "frames" / name.str())) {
                    samples.push_back({{"capture", captureFrame++},
                                       {"time", timeNow() - begun},
                                       {"street", streetFrame},
                                       {"frame", frame},
                                       {"clip", game.scene ? game.scene->image.id : ""},
                                       {"paused", game.paused},
                                       {"visual_time", visualTime},
                                       {"effects", effects.size()},
                                       {"run", attempts}});
                    captureNext = std::max(now, captureNext + 1. / 60.);
                }
            }
        }
        CampaignRecording::frame(renderer);
        check(SDL_RenderPresent(renderer));
        const auto ns = SDL_GetTicksNS();
        const double t = ns / 1e9;
        for (auto index : unpresentedShots) {
            auto &entry = trace.at(index);
            const double latency = 1000 * (t - entry.at("monotonic_seconds").get<double>());
            entry["first_feedback_submit_ms"] = latency;
            if (linyuan)
                submits.push_back(latency);
        }
        unpresentedShots.clear();
        if (feedbackForSubmit > 0) {
            submits.push_back(1000 * (t - feedbackForSubmit));
            feedbackForSubmit = 0;
        }
        if (switchPending) {
            ++switches;
            if (!evidence.empty())
                transitions.push_back({{"clip", game.scene->image.id},
                                       {"file", media.fileId()},
                                       {"generation", game.generation},
                                       {"street_frame", streetFrame},
                                       {"prepared", prepared},
                                       {"time", t - begun},
                                       {"from_input_ms", hitForSwitch > 0 ? Json(1000 * (t - hitForSwitch))
                                                                          : Json(nullptr)}});
            switchPending = false;
            hitForSwitch = 0;
        }
        if (game.screen == Screen::play) {
            visible = {ns, game.generation, frame, game.scene, picture};
            history.push_back(visible);
            while (ns - history.front().submitted > 300000000)
                history.pop_front();
            const auto *w = game.scene->window(frame);
            if (linyuan && !game.paused && closedWindowGeneration != game.generation &&
                !game.scene->windows.empty() && frame >= game.scene->windows.back().end) {
                closedWindowGeneration = game.generation;
                record("window_close", frame, game.generation, t);
            }
            if (linyuan && !game.paused && game.scene->warning >= 0 && frame >= game.scene->warning &&
                warningGeneration != game.generation) {
                warningGeneration = game.generation;
                record("warning", frame, game.generation, t);
            }
            if (linyuan && newFeedback && !game.paused && warningToneGeneration != game.generation && dangerProgress() >= 0) {
                warningToneGeneration = game.generation;
                record("warning_tone", frame, game.generation, t);
                scoreAudio.cue("warning");
            }
            if (linyuan && !game.paused && game.active(w) &&
                (lastWindowGeneration != game.generation || lastWindowBegin != w->begin)) {
                record("window_open", frame, game.generation, t);
                lastWindowGeneration = game.generation;
                lastWindowBegin = w->begin;
            }
            if (!game.paused && game.active(w) &&
                (w->kind == Kind::target || (linyuan && w->kind == Kind::projectile)) &&
                intervalFor[w->node] != -1) {
                auto &sample = intervals.at(intervalFor[w->node]);
                if (sample["t_open"].is_null()) {
                    sample["t_open"] = t - begun;
                    sample["wait_ms"] = 1000 * (t - begun - sample["t_hit"].get<double>());
                    sample["open_frame"] = frame;
                    sample["open_clip"] = game.scene->image.id;
                }
            }
        }
    }

    void pushKey(SDL_Keycode key) {
        SDL_Event event{};
        event.type = SDL_EVENT_KEY_DOWN;
        event.key.timestamp = SDL_GetTicksNS();
        event.key.windowID = SDL_GetWindowID(window);
        event.key.key = key;
        check(SDL_PushEvent(&event));
    }

    void driveLinyuan() {
        const Scene &scene = *game.scene;
        const Window *window = scene.window(frame);
        if ((scenario == "retry" || scenario == "give-up") && attempts == 1)
            return;
        if (scenario == "ordinary-timeout" && game.progress == 0 && game.hurts == 0)
            return;
        if (game.progress == retryNode && !game.hurts)
            return;
        if (scenario == "raft-timeout" && game.progress == 9 && game.hurts == 0)
            return;
        if (((scenario == "early-reload" && game.progress == 1) || (scenario == "normal" && game.progress == 2)) &&
            game.arrows < 8 && game.reloads == 0) {
            pushKey(SDLK_R);
            return;
        }
        if (scenario == "scan-early" && ((action == 0 && game.progress == 0) || (action == 1 && game.progress == 4)) &&
            scene.allowEarlyMiss &&
            !window && !scene.windows.empty() && frame < scene.windows.front().begin) {
            ++action;
            pushButton(scene.center(scene.windows.front().begin));
            return;
        }
        if (!game.arrows) {
            if (scenario == "empty" && action == 0 && game.active(window)) {
                ++action;
                pushButton(scene.center(frame));
                return;
            }
            if (scenario == "empty" && !action)
                return;
            pushKey(SDLK_R);
            return;
        }
        if (!game.active(window) || (pressGeneration == game.generation && !(game.hp == 1 &&
            encounter.nodes[game.progress].weakDamage == 2 && frame > armorFirstFrame)))
            return;
        if (window->kind == Kind::civilian) {
            if (scenario == "peddler-miss" && action == 0) {
                ++action;
                pushButton({40, 40});
            } else if ((scenario == "peddler-hit" || scenario == "civilian-hit") && action == 0) {
                ++action;
                pushButton({picture.x + scene.center(frame).x * picture.w / encounter.width,
                            picture.y + scene.center(frame).y * picture.h / encounter.height});
            }
            return;
        }
        if (scene.holdFrame >= 0 && scenario == "tutorial-hold" && action == 0) {
            if (visualTime < 1.8 || frame < scene.holdFrame)
                return;
            ++action;
        }
        if (window->kind == Kind::projectile) {
            if (scenario == "needle-core-closed" && action == 0) {
                const auto &core = encounter.scenes.at("elite_core");
                Point closed = core.center(core.image.start);
                if (scene.aimCovers(frame, closed, game.rules.aimRadius))
                    return;
                ++action;
                pushButton(closed);
                return;
            }
            if (scenario == "needle-miss" && game.hurts == 0)
                return;
            if (scenario == "needle-late" && frame < scene.windows.back().end - 1)
                return;
        } else if (scene.holdSeconds > 0) {
            if (scenario == "needle-repeat" && game.hp == 1 && game.blocks == 2)
                return;
        } else {
            const auto &windows = scene.windows;
            const auto &range = scenario == "early"  ? windows.front()
                                : scenario == "late" ? windows.back()
                                                     : windows[windows.size() / 2];
            int desired = scenario == "late"    ? range.end - 1
                          : scenario == "early" ? range.begin
                                                : (range.begin + range.end - 1) / 2;
            if (scene.holdFrame >= 0)
                desired = std::min(desired, scene.holdFrame);
            if (frame < desired)
                return;
        }
        if (scenario == "raft-miss" && game.progress == 9 && action == 0) {
            ++action;
            pushButton({encounter.width * .76, encounter.height * .62});
            return;
        }
        pressGeneration = game.generation;
        auto aim = scene.center(frame);
        if (!scene.weakArea.masks.empty()) {
            const bool wantWeak = scenario == "shoulder" || (scenario != "body" && scenario != "empty" &&
                scenario != "reload-held" && (encounter.nodes.size() == 11 || game.progress == 2 ||
                                               game.progress == 4 || game.progress == 6 || game.progress == 7));
            const auto &body = scene.image.masks.at(frame);
            const auto &weak = scene.weakArea.masks.at(frame);
            const auto &spans = wantWeak ? weak : body;
            int longest = 0;
            for (const auto &span : spans) {
                const int x = (span.x0 + span.x1) / 2;
                Point direct{2. * x + 1, 2. * span.y + 1};
                if (span.x1 - span.x0 > longest && scene.weakAt(frame, direct) == wantWeak) {
                    aim = direct;
                    longest = span.x1 - span.x0;
                }
            }
            if (!longest && (scenario == "shoulder" || !wantWeak)) {
                pressGeneration = -1;
                return;
            }
        }
        if (encounter.nodes[game.progress].weakDamage == 2)
            armorFirstFrame = frame;
        aim = {picture.x + aim.x * picture.w / encounter.width,
               picture.y + aim.y * picture.h / encounter.height};
        pushButton(aim);
        if (scenario == "frozen-input" && game.progress == 0)
            pushButton(aim);
    }

    void pushButton(Point point, Uint8 button = SDL_BUTTON_LEFT) {
        SDL_Event event{};
        event.type = SDL_EVENT_MOUSE_BUTTON_DOWN;
        event.button.timestamp = SDL_GetTicksNS();
        event.button.windowID = SDL_GetWindowID(window);
        event.button.button = button;
        SDL_RenderCoordinatesToWindow(renderer, float(point.x), float(point.y), &event.button.x,
                                      &event.button.y);
        check(SDL_PushEvent(&event));
    }

    void drive(double time) {
        if (game.screen == Screen::title) {
            if (time - clickAt > .50) {
                pushKey(SDLK_RETURN);
                clickAt = time;
            }
            return;
        }
        if (game.screen == Screen::complete) {
            if (scenario == "recovery" && action < 5) {
                ++action;
                pressGeneration = -1;
                pushKey(SDLK_ESCAPE);
                clickAt = time;
                return;
            }
            if (!completedAt)
                completedAt = time;
            if ((!streetMovie || (encounter.selectableDifficulty && scenario != "street-hold")) &&
                (!capture || time - completedAt > .7))
                running = false;
            return;
        }
        if (replayRecorded && game.screen == Screen::play) {
            while (replayIndex < replayInputs.size()) {
                const auto &entry = replayInputs.at(replayIndex);
                const int generation = entry.at("generation"), recordedFrame = entry.at("frame");
                if (game.generation < generation || frame < recordedFrame)
                    return;
                if (game.generation != generation || game.scene->image.id != entry.at("clip") ||
                    frame != recordedFrame)
                    throw std::runtime_error("Input replay missed " + entry.at("clip").get<std::string>() +
                                             " frame " + std::to_string(recordedFrame));
                const std::string action = entry.at("event");
                if (action == "reload_begin")
                    pushKey(SDLK_R);
                else {
                    const double x = entry.at("input_x"), y = entry.at("input_y");
                    pushButton({picture.x + x * picture.w / encounter.width,
                                picture.y + y * picture.h / encounter.height},
                               action.starts_with("thunder_") ? SDL_BUTTON_MIDDLE : SDL_BUTTON_LEFT);
                }
                ++replayIndex;
            }
            return;
        }
        if (game.screen == Screen::failed) {
            if (linyuan && scenario == "give-up") {
                SDL_Event stop{};
                stop.type = SDL_EVENT_QUIT;
                SDL_PushEvent(&stop);
                return;
            }
            if (linyuan && scenario == "retry") {
                pressGeneration = -1;
                pushKey(SDLK_RETURN);
                return;
            }
            if (scenario != "recovery")
                throw std::runtime_error("Unexpected replay failure");
            ++action;
            pressGeneration = -1;
            pushKey(SDLK_RETURN);
            return;
        }
        if (scenario == "recovery") {
            if (action == 0)
                return; // Fail the first playthrough on purpose.
            if (action == 1 && game.progress == 1) {
                ++action;
                pushKey(SDLK_ESCAPE);
                clickAt = time;
                return;
            }
            if (game.paused) {
                if (time - clickAt > .20) {
                    pushButton({10, 10}); // The pause menu ignores this click.
                    pushKey(SDLK_ESCAPE);
                    ++action;
                }
                return;
            }
            if (action == 3 && game.progress == 1 && game.pending.empty() && !game.reloadLeft) {
                ++action;
                pushKey(SDLK_R);
                return;
            }
        }
        if (linyuan && scenario == "reload-held" && game.reloadLeft > 0 && action == 0) {
            ++action;
            pushButton({500, 200});
        }
        if (!game.interactive() || frame < 0 || game.reloadLeft)
            return;
        const Scene &s = *game.scene;
        if (linyuan) {
            driveLinyuan();
            return;
        }
        if (scenario == "fx-reload" && action == 0 && game.progress == 1 && !effects.empty()) {
            ++action;
            pushKey(SDLK_R);
            return;
        }
        const auto *w = s.window(frame);
        if (game.arrows == 0) {
            pushKey(SDLK_R);
            return;
        }
        if (w && w->kind == Kind::civilian && scenario != "civilian-hit")
            return;
        if (!game.active(w)) {
            if (scenario == "early" && s.image.id.starts_with("lantern_to_wisp") && frame == 3 &&
                action == 0) {
                ++action;
                pushButton({200, 150});
            }
            if (scenario == "impact" && s.launch >= 0 && frame == s.impact && !attemptedImpact) {
                attemptedImpact = true;
                pushButton(s.center(frame - 1));
            }
            return;
        }
        if (pressGeneration == game.generation)
            return;
        if (scenario == "street-hold" &&
            ((w->node == 0 && game.hurts < 1) || (w->node == 1 && game.hurts < 2)))
            return;
        const bool intercept = scenario.starts_with("intercept-") || scenario == "impact";
        const bool buildingCharge = scenario == "charge" && game.energy < game.rules.charge;
        if (s.launch >= 0 && ((intercept && game.blocks + game.hurts == 0) || buildingCharge)) {
            if (w->kind != Kind::projectile || scenario == "impact")
                return;
            const auto boundaries = std::find_if(s.windows.begin(), s.windows.end(), [](const Window &v) {
                return v.kind == Kind::projectile;
            });
            const int wanted = scenario == "intercept-last"     ? s.impact - 1
                               : scenario == "intercept-middle" ? (boundaries->begin + s.impact) / 2
                                                                : boundaries->begin;
            if (frame != wanted)
                return;
        } else {
            if (w->kind == Kind::projectile)
                return;
            if (scenario != "early" &&
                (s.image.id.starts_with("lantern_to_wisp") || s.image.id == "wisp_to_fox"))
                return;
            int wanted = w->begin;
            if (w->node == 0) {
                const int end = s.impact >= 0 ? s.impact : s.image.frames - 1;
                wanted = scenario == "early" ? 2 : scenario == "late" ? end - 3 : end / 2;
                if (replayCut >= 0)
                    wanted = replayCut;
            } else if (encounter.selectableDifficulty && s.impact >= 0 && scenario == "normal") {
                // Sample the whole threat window, including different motion poses.
                const int first = s.windows.front().begin;
                const int last = s.launch >= 0 ? s.launch : s.impact;
                wanted = first + (last - first) * (1 + w->node % 3) / 4;
            } else if (scenario != "early") {
                wanted += 5;
            }
            if (frame < wanted)
                return;
        }
        pressGeneration = game.generation;
        clickAt = time;
        const bool thunder = encounter.nodes[w->node].hp > 1 && game.energy == game.rules.charge &&
                             (scenario == "charge" || scenario == "thunder" ||
                              (scenario == "thunder-finish" && game.hp == 2));
        pushButton(s.center(frame), thunder ? SDL_BUTTON_MIDDLE : SDL_BUTTON_LEFT);
        if (!thunder && encounter.nodes[w->node].hp > 1)
            pushButton(s.center(frame)); // Identical queued input during the hit freeze.
    }

    void report() {
        if (evidence.empty())
            return;
        const bool intercept = scenario.starts_with("intercept-");
        int ordinaryHits = 0;
        for (const auto &node : encounter.nodes)
            ordinaryHits += game.health(node);
        bool good = game.screen == Screen::complete && game.progress == int(encounter.nodes.size()) &&
                    (!encounter.street || (encounter.selectableDifficulty && scenario != "street-hold") ||
                     (streetFrame == encounter.street->frames - 1 && !streetMovie)) &&
                    (!intercept || (game.blocks == 1 && game.hurts == 0 && game.launches == 1)) &&
                    (scenario != "impact" || (game.blocks == 0 && game.hurts == 1 && attemptedImpact)) &&
                    (scenario != "recovery" || (attempts >= 3 && titleResident == 0)) &&
                    (scenario != "street-hold" || (encounter.street && game.hurts == 2 && game.lives == 1)) &&
                    (scenario != "fx-reload" || (effectFinishedDuringReload && game.reloads == 1)) &&
                    (scenario != "civilian-hit" || game.civilianHits > 0) &&
                    (scenario != "peddler-hit" || game.civilianHits > 0) &&
                    (scenario != "charge" ||
                     (game.blocks > 0 && game.hurts == 0 && game.hits == ordinaryHits + game.blocks - 2)) &&
                    (!scenario.starts_with("thunder") || game.hits == ordinaryHits - 2);
        Json assertions = Json::object();
        if (linyuan && automated && encounter.nodes.size() == 11) {
            auto count = [&](const std::string &name, const std::string &clip = "") {
                return std::count_if(trace.begin(), trace.end(), [&](const Json &e) {
                    return e.at("event") == name && (clip.empty() || e.at("clip") == clip);
                });
            };
            assertions["finished_eleven_nodes"] = game.progress == 11 && game.kills == 11;
            const int misses = int(scenario == "peddler-miss");
            const int civHits = int(scenario == "peddler-hit");
            assertions["spent_and_hit"] = game.shots == 11 + misses + civHits && game.hits == 11;
            assertions["forbearance_outcome"] =
                (scenario == "peddler-miss" || scenario == "peddler-hit")
                    ? count("forbearance_bonus") == 0
                    : count("forbearance_bonus") == 1;
            if (scenario == "peddler-hit")
                assertions["peddler_hurt"] = game.civilianHits == 1;
            if (scenario == "tutorial-hold")
                assertions["tutorial_held"] = std::any_of(trace.begin(), trace.end(), [](const Json &e) {
                    return e.at("event") == "shot_purify" && e.at("clip") == "wave_01" && e.at("time").get<double>() >= 1.8;
                });
            for (auto it = assertions.begin(); it != assertions.end(); ++it)
                good &= it.value().get<bool>();
        } else if (linyuan && automated && encounter.nodes.size() == 10 && scenario == "give-up") {
            assertions["quit_at_death"] = game.screen == Screen::failed && !game.lives && attempts == 1;
            good = assertions["quit_at_death"].get<bool>();
        } else if (linyuan && automated && encounter.nodes.size() == 10) {
            auto count = [&](const std::string &name, const std::string &clip = "") {
                return std::count_if(trace.begin(), trace.end(), [&](const Json &e) {
                    return e.at("event") == name && (clip.empty() || e.at("clip") == clip);
                });
            };
            auto visited = [&](const std::string &clip) {
                return std::count_if(transitions.begin(), transitions.end(),
                                     [&](const Json &t) { return t.at("clip") == clip; });
            };
            assertions["finished_ten_nodes"] = game.progress == 10 && game.kills == 11;
            const bool leaked = scenario == "needle-miss", repeated = scenario == "needle-repeat";
            const int misses = scenario == "scan-early" ? 2 : int(scenario == "raft-miss" || scenario == "needle-core-closed");
            const int armorChip = int(count("shot_hit", "wave_08"));
            const int expectedHits = 13 + int(repeated) + armorChip;
            assertions["spent_and_hit"] = game.shots == expectedHits + misses && game.hits == expectedHits;
            assertions["intercept_count"] = game.blocks == (repeated ? 3 : 2);
            assertions["two_core_exposures"] = count("shot_hit", "elite_core") == 1 &&
                count("shot_purify", "elite_core") == 1 && visited("elite_flinch") == 1 &&
                visited("elite_launch") == 1 + int(repeated) + int(leaked);
            int ammo = 8, refunds = 0;
            bool inventoryCorrect = true;
            for (const auto &e : trace) {
                if (e.at("attempt") != attempts)
                    continue;
                const auto name = e.at("event").get<std::string>();
                if (name == "start")
                    ammo = e.at("arrows").get<int>();
                if (name == "ready")
                    ammo = 8;
                if (name == "shot_hit" || name == "shot_purify" || name == "shot_miss" || name == "shot_intercept") {
                    const bool returned = (name == "shot_hit" || name == "shot_purify") && e.value("weak", false);
                    ammo -= !returned;
                    refunds += returned;
                    inventoryCorrect &= ammo >= 0 && ammo == e.at("arrows").get<int>();
                }
                if (name == "reload_begin")
                    inventoryCorrect &=
                        std::abs(e.at("duration_seconds").get<double>() -
                                 (.16 + .055 * (8 - ammo)) * (game.rules.reloadSeconds / .6)) < .00001;
            }
            assertions["sword_accounting"] = inventoryCorrect && ammo == game.arrows && refunds == game.weakReturns;
            const int expectedHarm =
                int(leaked || scenario == "ordinary-timeout" || scenario == "raft-timeout" || retryNode >= 0);
            assertions["damage_and_lives"] =
                game.hurts == expectedHarm && game.lives == (scenario == "retry" ? game.rules.lives
                                                             : startingLives > 0 ? startingLives
                                                                                 : game.rules.lives) -
                                                                expectedHarm;
            if (scenario == "normal")
                assertions["partial_recall"] = game.reloads == 1 && game.weakReturns >= 4 && armorChip == 0;
            if (scenario == "early" || scenario == "late" || scenario == "normal") {
                for (int i : {0, 1, 2, 3, 4, 5, 6, 7, 9}) {
                    const auto &clip = encounter.scenes.at(encounter.nodes[i].id);
                    const auto &ws = clip.windows;
                    if (ws.empty()) {
                        assertions["missing_windows"] = false;
                        continue;
                    }
                    const auto &expected = scenario == "early"  ? ws.front()
                                           : scenario == "late" ? ws.back()
                                                                : ws[ws.size() / 2];
                    assertions["cut_" + clip.image.id] = visited(expected.onHit) == 1;
                }
            }
            if (scenario == "scan-early") {
                for (const auto &id : {"wave_01","wave_05"}) {
                    const auto &fox = encounter.scenes.at(id);
                    assertions[std::string("pre_scan_miss_") + id] =
                    std::any_of(trace.begin(), trace.end(), [&](const Json &e) {
                        return e.at("clip") == id && e.at("event") == "shot_miss" &&
                               e.at("frame").get<int>() < fox.windows.front().begin && !e.at("weak").get<bool>();
                    });
                }
            }
            if (scenario == "needle-late")
                assertions["late_needle_cut"] = visited("elite_intercept_late") == 2;
            if (scenario == "needle-core-closed")
                assertions["closed_core_miss"] = std::any_of(trace.begin(), trace.end(),
                                                             [&](const Json &e) {
                                                                 return e.at("event") == "shot_miss" &&
                                                                        e.at("clip") == "wave_09" &&
                                                                        e.at("hp") == 2;
                                                             }) &&
                                                 game.blocks == 2;
            if (scenario == "needle-miss")
                assertions["missed_needle_damage"] =
                    visited("elite_impact") == 1 && count("hurt", "wave_09") == 1;
            if (scenario == "needle-repeat") {
                int first = 0, second = -1, third = -1;
                for (const auto &e : trace)
                    if (e.at("event") == "shot_intercept") {
                        if (e.at("intercepts") == 1)
                            first = e.at("score");
                        if (e.at("intercepts") == 2 && e.at("hp") == 1)
                            second = e.at("score");
                        if (e.at("intercepts") == 3 && e.at("hp") == 1)
                            third = e.at("score");
                    }
                assertions["repeat_retained_hp_and_no_bonus"] =
                    first > 0 && second == first + 150 && third == second && visited("elite_launch") == 2;
            }
            if (scenario == "raft-miss")
                assertions["raft_miss_then_hit"] =
                    count("shot_miss", "wave_10") == 1 && count("shot_purify", "wave_10") == 1;
            if (scenario == "raft-timeout")
                assertions["raft_timeout_reopen"] = visited("wave_10") == 2 && count("hurt", "wave_10") == 1;
            if (scenario == "ordinary-timeout")
                assertions["ordinary_timeout_reopen"] =
                    visited("wave_01") == 2 && count("hurt", "wave_01") == 1;
            if (retryNode >= 0) {
                const auto &id = encounter.nodes[retryNode].id;
                assertions["chosen_wave_closed_hurt_reopened"] = visited(id) == 2 &&
                    count("window_close", id) == 1 && count("hurt", id) == 1 && count("shot_purify", id) == 1;
            }
            if (scenario == "frozen-input")
                assertions["same_frame_duplicate_ignored"] = count("shot_ignored", "wave_01") == 1;
            if (scenario == "empty")
                assertions["empty_no_consumption"] = count("shot_empty") == 1 && game.reloads >= 1;
            if (scenario == "reload-held")
                assertions["press_while_reloading_ignored"] = count("shot_ignored") == 1 && game.reloads >= 1;
            if (scenario == "body" || scenario == "shoulder") {
                assertions["armor_body_or_direct_core"] = armorChip == int(scenario == "body");
                for (const auto &id : {"wave_01","wave_02","wave_03","wave_04","wave_05","wave_06","wave_07","wave_08"})
                    assertions[std::string("weak_area_") + id] =
                        std::any_of(trace.begin(), trace.end(), [&](const Json &e) {
                            return e.at("clip") == id && e.at("event") == "shot_purify" &&
                                   e.at("weak") == (scenario == "shoulder");
                        });
            }
            if (scenario == "retry")
                assertions["death_then_full_retry"] =
                    attempts == 2 && count("death") == 1 &&
                    std::count_if(trace.begin(), trace.end(), [&](const Json &e) {
                        return e.at("event") == "start" && e.at("score") == 0 && e.at("arrows") == 8 &&
                               e.at("lives") == game.rules.lives;
                    }) >= 1;
            if (scenario == "early-reload")
                assertions["early_reload_performed"] = std::any_of(trace.begin(), trace.end(), [&](const Json &e) {
                    return e.at("event") == "reload_begin" && e.at("arrows") == 7 &&
                           std::abs(e.at("duration_seconds").get<double>() -
                                    .215 * (game.rules.reloadSeconds / .6)) < .00001;
                });
            for (auto it = assertions.begin(); it != assertions.end(); ++it)
                good &= it.value().get<bool>();
        }
        const auto *display = SDL_GetCurrentDisplayMode(SDL_GetDisplayForWindow(window));
        Json payload = {{"ok", good},
                        {"assertions", assertions},
                        {"scenario", scenario},
                        {"difficulty", game.rules.id},
                        {"civilian_hits", game.civilianHits},
                        {"best_combo", game.bestCombo},
                        {"kills", game.kills},
                        {"arrows", game.arrows},
                        {"score", game.score},
                        {"renderer", SDL_GetRendererName(renderer)},
                        {"display_refresh_hz", display ? display->refresh_rate : 0.f},
                        {"feedback_version", newFeedback ? "new" : "old"},
                        {"reduced_flash", reducedFlash},
                        {"screen_shake", shakeEnabled},
                        {"capture_enabled", capture || CampaignRecording::enabled()},
                        {"audio_device", sound.available()},
                        {"seconds", timeNow() - begun},
                        {"play_seconds", completedAt - playStarted},
                        {"shots", game.shots},
                        {"hits", game.hits},
                        {"lives", game.lives},
                        {"hurts", game.hurts},
                        {"launches", game.launches},
                        {"intercepts", game.blocks},
                        {"weak_returns", game.weakReturns},
                        {"reloads", game.reloads},
                        {"attempts", attempts},
                        {"rejected", rejected},
                        {"switches", switches},
                        {"movies_peak", totalMoviesPeak},
                        {"action_movies_peak", media.highCount},
                        {"media_payload_peak_bytes", payloadPeak},
                        {"video_texture_yuv420_bytes", size_t(encounter.width) * encounter.height * 3 / 2},
                        {"foreground_texture_bgra_bytes",
                         encounter.street ? size_t(encounter.width) * encounter.height * 4 : 0},
                        {"process_peak_working_set_bytes", processPeak},
                        {"movie_evictions", media.evictions},
                        {"street_frame", streetFrame},
                        {"street_decoder_live", bool(streetMovie)},
                        {"effect_finished_during_reload", effectFinishedDuringReload},
                        {"captures", samples},
                        {"capture_target_hz", 60},
                        {"title_resident_movies", titleResident},
                        {"feedback_submit_ms", submits},
                        {"intervals", intervals},
                        {"transitions", transitions},
                        {"events", trace}};
        if (replayRecorded) {
            Json actual = Json::array();
            for (const auto &entry : trace) {
                const auto action = entry.at("event").get<std::string>();
                if (action.starts_with("shot_") || action.starts_with("thunder_") || action == "reload_begin")
                    actual.push_back({entry.at("event"), entry.at("clip"), entry.at("frame"),
                                      entry.at("arrows"), entry.at("lives")});
            }
            Json expected = Json::array();
            for (const auto &entry : replayInputs)
                expected.push_back({entry.at("event"), entry.at("clip"), entry.at("frame"), entry.at("arrows"),
                                    entry.at("lives")});
            good &= replayIndex == replayInputs.size() && actual == expected;
            payload["assertions"]["recorded_inputs_reproduced"] = actual == expected;
            payload["ok"] = good;
        }
        std::ofstream(evidence / "playthrough.json") << payload.dump(2) << '\n';
        if (!good && automated)
            throw std::runtime_error("Replay assertions failed: " + scenario);
    }

    void loadInputs(const fs::path &file) {
        std::ifstream stream(file);
        if (!stream)
            throw std::runtime_error("Missing recorded encounter inputs: " + file.string());
        const auto log = Json::parse(stream);
        for (const auto &entry : log.at("events")) {
            const auto action = entry.at("event").get<std::string>();
            if (action.starts_with("shot_") || action.starts_with("thunder_") || action == "reload_begin") {
                if (action != "reload_begin" && (!entry.contains("input_x") || !entry.contains("input_y")))
                    throw std::runtime_error("Input recording lacks source coordinates: " + file.string());
                replayInputs.push_back(entry);
            }
        }
        replayRecorded = true;
    }

    void run() {
        CampaignRecording::Audio recorded(sound, 210);
        if (capture && !evidence.empty())
            sound.startCapture();
        visualTick = previousTick = begun = captureNext = clickAt = timeNow();
        if (campaignFight)
            restart();
        while (running) {
            if (campaignFight && game.screen == Screen::complete)
                return;
            const double tick = timeNow();
            if (game.screen != Screen::title && !game.paused)
                visualTime += newFeedback ? std::max(0., tick - visualTick)
                                          : std::clamp(tick - visualTick, 0., 1. / 24);
            visualTick = tick;
            std::erase_if(effects, [&](const VisualCue &cue) {
                if (visualTime - cue.start < (newFeedback && cue.kind == Cue::hurt ? .78 : .45))
                    return false;
                if (!evidence.empty()) {
                    if (cue.kind == Cue::purify && game.reloadLeft > 0)
                        effectFinishedDuringReload = true;
                    record("effect_end_" + cueName(cue.kind), frame, game.generation, tick);
                }
                return true;
            });
            events();
            const double now = timeNow();
            if (visible.scene && game.screen == Screen::play) {
                const int before = game.launches;
                const int beforeScore = game.score;
                const Cue cue = game.present(visible.generation, visible.frame);
                if (game.score > beforeScore && cue == Cue::none) {
                    record("forbearance_bonus", visible.frame, visible.generation, now);
                    if (!evidence.empty())
                        trace.back()["bonus"] = game.score - beforeScore;
                }
                if (game.launches != before)
                    record("launch", visible.frame, visible.generation, now);
                if (cue != Cue::none) {
                    record(cueName(cue), visible.frame, visible.generation, now);
                    feedback(cue, {}, now);
                }
            }
            const double step = linyuan ? std::max(0., now - previousTick) : std::min(.06, now - previousTick);
            if (const Cue cue = game.tick(step, now); cue != Cue::none) {
                record(cueName(cue), frame, game.generation, now);
                feedback(cue, cursor, now);
            }
            previousTick = now;
            if (game.screen == Screen::failed && !defeatedAt) {
                stopSpeech("defeat");
                defeatedAt = now;
                record("death", frame, game.generation, now);
            }
            sync(now);
            combatSpeech();
            if (linyuan && newFeedback) {
                // Let a fresh strike clear the music briefly. An overlapping weaker cue
                // must not release a stronger duck in the middle of a damage sound.
                float musicScale = 1.f;
                for (const auto &cue : effects) {
                    const bool hurt = cue.kind == Cue::hurt;
                    if (!hurt && !cue.tier)
                        continue;
                    const double duration = hurt ? .42 : cue.tier == 3 ? .30 : .15;
                    const float envelope = float(std::clamp((duration - (visualTime - cue.start)) / (duration * .66), 0., 1.));
                    const float depth = hurt ? .44f : cue.tier == 3 ? .30f : .21f;
                    musicScale = std::min(musicScale, 1.f - depth * envelope);
                }
                scoreAudio.scaleMusic(musicScale);
            }
            scoreAudio.update(game.screen == Screen::play && !game.paused);
            ambience.update(game.screen == Screen::play && !game.paused);
            syncStreet();
            render(timeNow());
            warmNext();
            if (automated) {
                totalMoviesPeak = std::max(totalMoviesPeak, media.count() + int(bool(streetMovie)));
                payloadPeak = std::max(payloadPeak, media.payloadBytes() +
                                                        (streetMovie ? streetMovie->payloadBytes() : 0));
                PROCESS_MEMORY_COUNTERS counter{};
                if (GetProcessMemoryInfo(GetCurrentProcess(), &counter, sizeof(counter)))
                    processPeak = std::max(processPeak, counter.PeakWorkingSetSize);
                // Reading the presented surface and waiting on media can extend an offline replay.
                const bool extendedTimeout = linyuan || capture || CampaignRecording::enabled() ||
                                             scenario == "charge" || scenario == "recovery";
                if (now - begun > (extendedTimeout ? 180. : 55.))
                    throw std::runtime_error("Replay timed out: " + scenario);
                drive(timeNow());
            }
            SDL_Delay(1);
        }
        if (capture && !evidence.empty()) {
            frameWriter->finish();
            frameWriter->check();
            sound.finishCapture(evidence, begun);
        }
        report();
    }
};
MenuChoice linyuanScreen(SDL_Renderer *renderer, const Campaign &campaign, const Progress &state,
                         SDL_Texture *backdrop, double seconds, bool automated, const fs::path &evidence) {
    const bool complete = state.next == "@complete";
    Ink ink(renderer);
    const auto start = SDL_GetTicks();
    ChapterScore total;
    bool saved = false;
    for (const auto &[chapter, score] : state.scores)
        total.add(score);
    for (;;) {
        SDL_SetRenderDrawColor(renderer, 18, 33, 30, 255);
        SDL_RenderClear(renderer);
        if (complete && backdrop)
            SDL_RenderTexture(renderer, backdrop, nullptr, nullptr);
        ink.box(180, 150, 920, 390, {14, 29, 30, 219});
        ink.text(640, 190, 58, complete ? "竹海 · 战果" : campaign.title, ivory, true);
        if (complete) {
            const auto accuracy =
                total.shots ? std::to_string(std::lround(100. * total.hits / total.shots)) + "%" : "—";
            ink.text(640, 308, 25,
                     "得分 " + std::to_string(total.points) + "     命中率 " + accuracy + "     扣命 " +
                         std::to_string(total.damage) + "     用时 " +
                         std::to_string(int(std::lround(seconds))) + " 秒",
                     ivory, true);
        } else {
            ink.text(640, 291, 25, "左键出剑    右键或 R 收剑    Esc 暂停", ivory, true);
            ink.text(640, 341, 20, "刺穿琥珀弱点，飞剑自行回匣", gold, true);
        }
        ink.box(309, 395, 270, 68, {155, 114, 63, 255});
        ink.box(701, 395, 270, 68, {155, 114, 63, 255});
        ink.text(444, 413, 24, complete ? "再打一局" : "开始", ivory, true);
        ink.text(836, 413, 24, "结束", ivory, true);
        if (automated && !saved && !evidence.empty()) {
            const auto file = (evidence / (complete ? "results.bmp" : "title.bmp")).u8string();
            std::unique_ptr<SDL_Surface, decltype(&SDL_DestroySurface)> surface(
                SDL_RenderReadPixels(renderer, nullptr), SDL_DestroySurface);
            if (!surface || !SDL_SaveBMP(surface.get(), reinterpret_cast<const char *>(file.c_str())))
                throw std::runtime_error("Cannot save menu capture: " + std::string(SDL_GetError()));
            saved = true;
        }
        CampaignRecording::frame(renderer);
        SDL_RenderPresent(renderer);
        if (automated && SDL_GetTicks() - start >= (CampaignRecording::enabled() ? 1250u : 0u))
            return complete ? MenuChoice::quit : MenuChoice::newGame;
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT)
                return MenuChoice::quit;
            if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {
                if (e.key.key == SDLK_ESCAPE)
                    return MenuChoice::quit;
                if (e.key.key == SDLK_RETURN)
                    return MenuChoice::newGame;
            }
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button == SDL_BUTTON_LEFT) {
                SDL_ConvertEventToRenderCoordinates(renderer, &e);
                if (e.button.y < 395 || e.button.y > 463)
                    continue;
                if (e.button.x >= 309 && e.button.x <= 579)
                    return MenuChoice::newGame;
                if (e.button.x >= 701 && e.button.x <= 971)
                    return MenuChoice::quit;
            }
        }
        SDL_Delay(10);
    }
}

void runCampaign(SDL_Window *window, SDL_Renderer *renderer, const CampaignWorld &world,
                 const std::string &name, const fs::path &logRoot, const std::string &difficultyId,
                 bool gunMode, const std::string &scenario, bool capture, bool humanLog, bool newFeedback,
                 bool reducedFlash, bool shakeEnabled, const fs::path &inputSource) {
    const bool isMvp = world.linyuan() && name == "mvp";
    fs::path evidence = logRoot;
    const bool automated = !evidence.empty() && !humanLog;
    if (!evidence.empty())
        fs::create_directories(evidence);
    std::optional<CampaignRecording> recording;
    if (capture) {
        if (evidence.empty())
            throw std::runtime_error("Campaign capture requires --smoke <directory>");
        recording.emplace(evidence / "recording");
    }
    Campaign campaign(world, name);
    fs::path save;
    if (!isMvp && evidence.empty()) {
        std::unique_ptr<char, decltype(&SDL_free)> dir(
            SDL_GetPrefPath(world.linyuan() ? "Linyuan" : "Changan",
                            world.linyuan() ? "FlyingSwords" : "Lanterns"),
            SDL_free);
        if (!dir)
            throw std::runtime_error(SDL_GetError());
        save = fs::path(reinterpret_cast<const char8_t *>(dir.get())) / (name + ".json");
    } else if (!isMvp) {
        save = evidence / "checkpoint.json";
    }
    Progress state = save.empty() ? Progress{} : Progress::load(save);
    if (state.next.empty())
        state.difficulty = difficultyId;
    difficulty(state.difficulty);
    campaign.locate(state.next);
    Receiver receiver;
    if (gunMode && !receiver.open())
        throw std::runtime_error("Cannot open TVGun ports");
    Receiver *gun = gunMode ? &receiver : nullptr;
    Sound campaignDevice;
    ScoreAudio score;
    const auto audioFolder = world.assets() / "audio";
    score.open(campaignDevice.device(), audioFolder, true, world.linyuan() ? "" : "festival");
    Json timeline = Json::array();
    const auto begun = timeNow();
    double sessionStart = begun, sessionSeconds = 0;
    int runNumber = 0;
    Texture resultBackground{nullptr, SDL_DestroyTexture};
    bool quit = false;
    while (!quit) {
        const auto menuTheme =
            audioFolder / "music" / (state.next == "@complete" ? "credits.wav" : "title.wav");
        const bool hasTitle = fs::is_regular_file(menuTheme);
        if (hasTitle)
            score.selectTrack(menuTheme);
        std::optional<CampaignRecording::Audio> menuAudio;
        if (recording)
            menuAudio.emplace(campaignDevice, 30);
        auto choice = isMvp ? linyuanScreen(renderer, campaign, state, resultBackground.get(),
                                            sessionSeconds, automated, evidence)
                            : campaignMenu(renderer, campaign, state, gun, automated,
                                           hasTitle ? &score : nullptr);
        if (world.linyuan() && !evidence.empty()) {
            std::ofstream(logRoot / "choices.jsonl", std::ios::app)
                << Json{{"event", state.next == "@complete" ? (choice == MenuChoice::quit ? "finish" : "replay")
                                                            : (choice == MenuChoice::quit ? "quit" : "start")},
                        {"run", state.next.empty() ? runNumber + 1 : runNumber},
                        {"time", timeNow() - begun},
                        {"automated", automated}}
                       .dump()
                << '\n';
        }
        menuAudio.reset();
        score.update(false);
        if (evidence.empty() && choice != MenuChoice::newGame)
            state.save(save);
        if (choice == MenuChoice::quit)
            break;
        if (choice == MenuChoice::newGame) {
            ++runNumber;
            if (isMvp && humanLog) {
                evidence = logRoot / ("run_" + std::to_string(runNumber));
                fs::create_directories(evidence);
                timeline = Json::array();
            }
            sessionStart = timeNow();
            state.pausedSeconds = 0;
            resultBackground.reset();
            state.scores.clear();
            state.lastStoryCivilian = false;
            state.energy = 0;
            state.arrows = 8;
            state.reloadRemaining = 0;
            state.next = campaign.stages.front().id;
            state.lives = difficulty(state.difficulty).lives;
            state.save(save);
        }
        score.volume(state.musicVolume / 100.f, state.effectsVolume / 100.f);
        for (size_t n = campaign.locate(state.next); n < campaign.stages.size(); ++n) {
            CampaignRecording::Audio background(campaignDevice, 240);
            const auto &stage = campaign.stages[n];
            bool skipped = false;
            Json playedFilms = Json::array();
            int completedReloads = 0;
            const auto opened = timeNow();
            ScoreAudio *music = nullptr;
            if (!stage.music.empty() && stage.level.empty()) {
                score.selectTrack(audioFolder / "music" / (stage.music + ".wav"));
                music = &score;
            } else {
                score.update(false);
            }
            if (stage.cardMillis) {
                Ink ink(renderer);
                const auto end = SDL_GetTicks() + stage.cardMillis;
                while (SDL_GetTicks() < end && !quit) {
                    SDL_Event event;
                    while (SDL_PollEvent(&event))
                        if (event.type == SDL_EVENT_QUIT)
                            quit = true;
                    SDL_SetRenderDrawColor(renderer, 12, 22, 22, 255);
                    SDL_RenderClear(renderer);
                    if (world.linyuan()) {
                        ink.box(420, 304, 440, 2, {204, 158, 86, 160});
                        ink.box(420, 392, 440, 2, {204, 158, 86, 160});
                    }
                    ink.text(640, 329, 36, stage.cardText, ivory, true);
                    CampaignRecording::frame(renderer);
                    SDL_RenderPresent(renderer);
                    SDL_Delay(8);
                }
                if (quit)
                    break;
            } else if (!stage.trial.is_null()) {
                if (!isMvp && world.linyuan() && stage.id == "taotie") {
                    state.arrows = 8;
                    state.reloadRemaining = 0;
                }
                // Preserve a story sword's sound tail across its outcome cut, even on a stage without a soundtrack.
                ScoreAudio storyFoley;
                ScoreAudio *trialAudio = music;
                if (world.linyuan() && !trialAudio) {
                    storyFoley.open(campaignDevice.device(), audioFolder, false);
                    storyFoley.volume(0.f, state.effectsVolume / 100.f);
                    trialAudio = &storyFoley;
                }
                if (playTrial(window, renderer, world, stage, state, gun, automated, evidence, scenario, trialAudio,
                              completedReloads, newFeedback, reducedFlash,
                              inputSource.empty() ? fs::path{} : inputSource / (stage.id + ".json"), shakeEnabled) ==
                    FilmEnd::quit) {
                    quit = true;
                    break;
                }
            } else if (stage.level.empty()) {
                for (auto film : stage.films) {
                    if (film.afterCivilian && *film.afterCivilian != state.lastStoryCivilian)
                        continue;
                    if (!evidence.empty())
                        playedFilms.push_back({{"take", film.take}, {"voice", film.voice}});
                    film.autoSkip = scenario == "skip-cg";
                    auto end = playFilm(
                        window, renderer, world.assets() / "drama", film, state.subtitles, gun, automated,
                        nullptr, music, state.voiceVolume / 100.f, state.effectsVolume / 100.f,
                        {&state.arrows, &state.reloadRemaining, difficulty(state.difficulty).reloadSeconds,
                         &completedReloads, &state.pausedSeconds});
                    if (end == FilmEnd::quit)
                        quit = true;
                    if (end == FilmEnd::skipped)
                        skipped = true;
                    if (end != FilmEnd::finished)
                        break;
                }
                if (quit)
                    break;
            } else {
                if (!isMvp && world.linyuan()) {
                    state.arrows = 8;
                    state.reloadRemaining = 0;
                }
                Encounter level(world.data() / stage.level);
                App fight(window, renderer, world.assets() / stage.level, std::move(level),
                          evidence.empty() ? fs::path{} : evidence / stage.id,
                          world.linyuan() ? scenario : "normal", false, gun, world.linyuan(), newFeedback,
                          reducedFlash, humanLog, stage.allowSpecial);
                fight.game.rules = difficulty(state.difficulty);
                fight.shakeEnabled = shakeEnabled;
                if (!inputSource.empty())
                    fight.loadInputs(inputSource / stage.id / "playthrough.json");
                fight.speechGain = state.voiceVolume / 100.f;
                fight.campaignFight = true;
                if (!stage.music.empty()) {
                    if (!world.linyuan() && !fight.encounter.selectableDifficulty)
                        fight.scoreAudio.open(fight.sound.device(), audioFolder, true,
                                              world.linyuan() ? "" : "festival");
                    fight.scoreAudio.selectTrack(audioFolder / "music" / (stage.music + ".wav"));
                }
                fight.scoreAudio.volume(state.musicVolume / 100.f * (world.linyuan() ? 1.2f : 1.f),
                                        state.effectsVolume / 100.f);
                if (world.linyuan())
                    fight.ambience.volume(.2875f * state.effectsVolume / 100.f, 0.f);
                fight.startingLives = std::clamp(state.lives, 1, fight.game.rules.lives);
                fight.startingEnergy = std::clamp(state.energy, 0, fight.game.rules.charge);
                fight.startingArrows = state.arrows;
                fight.startingReload = state.reloadRemaining;
                SDL_HideCursor();
                fight.run();
                state.pausedSeconds += fight.menuSeconds;
                SDL_ShowCursor();
                if (fight.game.screen != Screen::complete) {
                    if (world.linyuan() && !evidence.empty())
                        std::ofstream(logRoot / "choices.jsonl", std::ios::app)
                            << Json{{"event", fight.game.screen == Screen::failed ? "give_up" : "quit"},
                                    {"run", runNumber},
                                    {"time", timeNow() - begun},
                                    {"automated", automated}}
                                   .dump()
                            << '\n';
                    quit = !fight.returnToMenu;
                    break;
                }
                auto &g = fight.game;
                if (world.linyuan())
                    resultBackground = std::move(fight.texture);
                completedReloads = g.reloads;
                state.scores[stage.chapter].add({g.score, g.hits, g.shots, g.bestCombo,
                                                 g.hurts + g.civilianHits * g.rules.civilianDamage,
                                                 world.linyuan() ? g.kills : g.progress});
                state.lives = g.lives;
                state.energy = g.energy;
                state.arrows = g.arrows;
                state.reloadRemaining = g.reloadLeft;
                if (!evidence.empty()) {
                    fight.completedAt = timeNow();
                    fight.report();
                }
            }
            if (n + 1 < campaign.stages.size()) {
                const auto &next = campaign.stages[n + 1];
                state.next = next.id;
                if (next.chapter != stage.chapter) {
                    state.lives = difficulty(state.difficulty).lives;
                    state.arrows = 8;
                    state.reloadRemaining = 0;
                }
            } else {
                state.next = "@complete";
                sessionSeconds = timeNow() - sessionStart - state.pausedSeconds;
                if (world.linyuan() && !evidence.empty()) {
                    const auto &total = state.scores[stage.chapter];
                    std::ofstream(evidence / "result.json")
                        << Json{{"run", runNumber},          {"points", total.points},
                                {"hits", total.hits},        {"shots", total.shots},
                                {"damage", total.damage},    {"kills", total.purified},
                                {"lives", state.lives},      {"arrows", state.arrows},
                                {"seconds", sessionSeconds}, {"paused_seconds", state.pausedSeconds}}
                               .dump(2);
                }
            }
            state.save(save);
            if (!evidence.empty()) {
                timeline.push_back({{"chapter", stage.chapter},
                                    {"stage", stage.id},
                                    {"opened", opened - begun},
                                    {"ended", timeNow() - begun},
                                    {"next", state.next},
                                    {"lives", state.lives},
                                    {"energy", state.energy},
                                    {"arrows", state.arrows},
                                    {"reloads", completedReloads},
                                    {"skipped", skipped},
                                    {"difficulty", state.difficulty}});
                if (!playedFilms.empty())
                    timeline.back()["films"] = std::move(playedFilms);
                std::ofstream(evidence / "timeline.json") << timeline.dump(2) << '\n';
            }
            if ((isMvp && scenario == "quit-after-s5") ||
                (!isMvp && scenario == "checkpoint-interrupt" && stage.id == "bamboo_card")) {
                state.save(save);
                quit = true;
                break;
            }
            if (!isMvp &&
                (n + 1 == campaign.stages.size() || campaign.stages[n + 1].chapter != stage.chapter)) {
                if (!chapterResults(renderer, stage, state.scores[stage.chapter], gun, automated, music,
                                    world.linyuan(), campaign.titleArt)) {
                    quit = true;
                    break;
                }
            }
        }
        score.update(false);
    }
    if (recording)
        recording->finish();
}
} // namespace
} // namespace ca

int wmain(int argc, wchar_t **argv) {
    using namespace ca;
    fs::path root, out, inputSource;
    std::string scenario = "normal", levelId, campaignId, difficultyId = "normal";
#ifdef DEFAULT_LINYUAN_WORLD
    std::string worldId = "linyuan";
#else
    std::string worldId = "changan";
#endif
    std::string feedback = "default";
    bool capture = false, gunMode = false, reducedFlash = false, humanLog = false, shakeEnabled = true;
    for (int i = 1; i < argc; ++i) {
        const std::wstring arg = argv[i];
        if (arg == L"--root" && i + 1 < argc)
            root = fs::absolute(argv[++i]);
        else if (arg == L"--world" && i + 1 < argc)
            worldId = fs::path(argv[++i]).string();
        else if (arg == L"--feedback" && i + 1 < argc)
            feedback = fs::path(argv[++i]).string();
        else if (arg == L"--reduced-flash")
            reducedFlash = true;
        else if (arg == L"--no-shake")
            shakeEnabled = false;
        else if (arg == L"--input-replay" && i + 1 < argc)
            inputSource = fs::absolute(argv[++i]);
        else if ((arg == L"--smoke" || arg == L"--log") && i + 1 < argc) {
            humanLog = arg == L"--log";
            out = fs::absolute(argv[++i]);
        } else if (arg == L"--difficulty" && i + 1 < argc) {
            const auto name = fs::path(argv[++i]).u8string();
            difficultyId.assign(reinterpret_cast<const char *>(name.data()), name.size());
        } else if (arg == L"--campaign" && i + 1 < argc) {
            const auto name = fs::path(argv[++i]).u8string();
            campaignId.assign(reinterpret_cast<const char *>(name.data()), name.size());
        } else if (arg == L"--level" && i + 1 < argc) {
            const auto name = fs::path(argv[++i]).u8string();
            levelId.assign(reinterpret_cast<const char *>(name.data()), name.size());
        } else if (arg == L"--scenario" && i + 1 < argc) {
            const auto name = fs::path(argv[++i]).u8string();
            scenario.assign(reinterpret_cast<const char *>(name.data()), name.size());
        } else if (arg == L"--tvgun")
            gunMode = true;
        else if (arg == L"--capture")
            capture = true;
    }
    try {
        SDL_SetMainReady();
        check(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMEPAD));
        if (root.empty())
            root = fs::path(reinterpret_cast<const char8_t *>(SDL_GetBasePath()));
        if (!inputSource.empty() && (out.empty() || humanLog))
            throw std::runtime_error("Input replay requires --smoke <output directory>");
        if (worldId != "changan" && worldId != "linyuan")
            throw std::runtime_error("Unknown campaign world: " + worldId);
        if (feedback != "default" && feedback != "old" && feedback != "new")
            throw std::runtime_error("Unknown feedback style: " + feedback);
        const CampaignWorld world{root, worldId};
        const bool newFeedback = feedback == "new" || (feedback == "default" && world.linyuan());
        if (levelId.empty() && campaignId.empty()) {
            std::ifstream manifest(world.data() / "start.json");
            if (!manifest && world.linyuan())
                throw std::runtime_error("Missing worlds/linyuan/start.json");
            const Json start = manifest ? Json::parse(manifest) : Json{{"level", "m0"}};
            levelId = start.value("level", "");
            campaignId = start.value("campaign", "");
        }
        if (world.linyuan() && campaignId == "mvp" && difficultyId != "normal")
            throw std::runtime_error("The Linyuan MVP supports normal difficulty");
        if (campaignId.empty() &&
            (levelId.empty() ||
             levelId.find_first_not_of("0123456789abcdefghijklmnopqrstuvwxyz_") != std::string::npos))
            throw std::runtime_error("Invalid encounter name");
        std::optional<Encounter> sizing;
        if (campaignId.empty())
            sizing.emplace(world.data() / levelId);
        SDL_SetHint(SDL_HINT_RENDER_VSYNC, "1");
        std::unique_ptr<SDL_Window, decltype(&SDL_DestroyWindow)> w(
            SDL_CreateWindow(world.linyuan() ? "临渊御剑" : "长安灯妖录", 1280, 720,
                             SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY |
                                 (out.empty() || humanLog ? 0 : SDL_WINDOW_HIDDEN)),
            SDL_DestroyWindow);
        check(bool(w));
        std::unique_ptr<SDL_Renderer, decltype(&SDL_DestroyRenderer)> r(
            SDL_CreateRenderer(w.get(), "opengl"), SDL_DestroyRenderer);
        if (!r)
            r.reset(SDL_CreateRenderer(w.get(), nullptr));
        check(bool(r));
        check(SDL_SetRenderDrawBlendMode(r.get(), SDL_BLENDMODE_BLEND));
        check(SDL_SetRenderLogicalPresentation(r.get(), sizing ? sizing->width : 1280,
                                               sizing ? sizing->height : 720,
                                               SDL_LOGICAL_PRESENTATION_LETTERBOX));
        SDL_HideCursor();
        if (!campaignId.empty()) {
            SDL_ShowCursor();
            runCampaign(w.get(), r.get(), world, campaignId, out, difficultyId, gunMode, scenario, capture,
                        humanLog, newFeedback, reducedFlash, shakeEnabled, inputSource);
        } else {
            App app(w.get(), r.get(), world.assets() / levelId, std::move(*sizing), out, scenario, capture,
                    nullptr, world.linyuan(), newFeedback, reducedFlash, humanLog);
            app.shakeEnabled = shakeEnabled;
            if (!inputSource.empty())
                app.loadInputs(inputSource / "playthrough.json");
            if (gunMode)
                app.setGunMode(true);
            if (app.encounter.selectableDifficulty)
                app.game.rules = difficulty(difficultyId);
            else if (difficultyId != "normal")
                throw std::runtime_error("This encounter supports normal difficulty only");
            app.run();
        }
    } catch (const std::exception &error) {
        if (!out.empty()) {
            fs::create_directories(out);
            std::ofstream(out / "error.txt") << error.what() << '\n';
        } else {
            SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, worldId == "linyuan" ? "临渊御剑" : "长安灯妖录",
                                     error.what(), nullptr);
        }
        SDL_Quit();
        return 1;
    }
    SDL_Quit();
    return 0;
}
