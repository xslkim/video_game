#include "changan_game.hpp"
#include "changan_record.hpp"
#include "changan_story.hpp"
#include "sound.hpp"
#include "tvgun.hpp"
#include "ui.hpp"
#include <SDL3/SDL_main.h>
#include <bcrypt.h>
#include <deque>
#include <iomanip>
#include <limits>
#include <psapi.h>
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
};

struct VisualCue {
    Cue kind;
    Point point;
    double start;
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
    Receiver ownReceiver;
    Receiver &receiver;
    bool gunMode = false;
    bool campaignFight = false, returnToMenu = false;
    int startingLives = 0, startingEnergy = 0, startingArrows = 8;
    double startingReload = 0;
    Texture texture{nullptr, SDL_DestroyTexture}, streetTexture{nullptr, SDL_DestroyTexture};
    fs::path streetFile;
    std::unique_ptr<Movie> streetMovie;
    int streetFrame = -1;
    double actionRate = 1;
    double playStarted = 0;
    fs::path evidence;
    std::string scenario;
    bool capture, dev = false, running = true, holding = false, fullscreen = false;
    std::deque<Stamp> history;
    Stamp visible;
    const MovieEntry *pendingEntry = nullptr;
    Point cursor{-100, -100};
    std::vector<VisualCue> effects;
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

    App(SDL_Window *w, SDL_Renderer *r, const fs::path &assets, Encounter level, fs::path out,
        std::string test, bool record, Receiver *sharedReceiver = nullptr)
        : window(w), renderer(r), encounter(std::move(level)), game(encounter), media(encounter, assets),
          ink(r), receiver(sharedReceiver ? *sharedReceiver : ownReceiver),
          gunMode(sharedReceiver != nullptr), evidence(std::move(out)), scenario(std::move(test)),
          capture(record), intervalFor(encounter.nodes.size(), -1) {
        if (encounter.selectableDifficulty)
            scoreAudio.open(sound.device(), assets.parent_path() / "audio");
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
            if (capture)
                fs::create_directories(evidence / "frames");
        }
    }

    void record(const std::string &name, int f, int gen, double when) {
        if (evidence.empty())
            return;
        trace.push_back({{"event", name},
                         {"time", when - begun},
                         {"clip", game.scene ? game.scene->image.id : ""},
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
        startStreet();
        visualTime = 0;
        visualTick = timeNow();
        playStarted = visualTick;
        std::fill(intervalFor.begin(), intervalFor.end(), -1);
        record("start", -1, game.generation, timeNow());
    }

    void goTitle() {
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
        if (game.paused)
            pauseAt = now;
        else if (!game.pending.empty())
            game.frozenUntil += now - pauseAt;
        record(game.paused ? "pause" : "resume", frame, game.generation, now);
    }

    void feedback(Cue c, Point point, double timestamp) {
        if (c == Cue::none)
            return;
        if (c != Cue::reload && c != Cue::ready)
            effects.push_back({c, point, visualTime});
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
        if (!scoreAudio.cue(c == Cue::empty ? "ready" : cueName(c)))
            sound.cue(tone);
        if (!evidence.empty())
            feedbackForSubmit = timestamp;
    }

    void shot(Point point, uint64_t ns, bool thunder) {
        auto f = std::find_if(history.rbegin(), history.rend(),
                              [ns](const Stamp &s) { return s.submitted <= ns; });
        if (f == history.rend() || ns - f->submitted > 300000000 || f->generation != game.generation)
            return;
        const double time = ns / 1e9;
        const auto *w = f->scene->window(f->frame);
        const int wasNode = game.progress;
        const int before = game.shots;
        Cue cue = game.input(point, f->generation, f->frame, thunder, timeNow());
        if (game.shots > before)
            scoreAudio.cue("shot");
        if (game.shots > before && w && w->kind == Kind::target && wasNode < int(intervalFor.size()) &&
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
        feedback(cue, location, time);
        record(thunder ? "thunder_" + cueName(cue) : "shot_" + cueName(cue), f->frame, f->generation, time);
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
            const auto type = event.type;
            if (type == SDL_EVENT_QUIT)
                running = false;
            if (type == SDL_EVENT_WINDOW_FOCUS_LOST && evidence.empty() && !game.paused)
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
                    if (cursor.x >= 68 && cursor.x <= 388 && cursor.y >= 401 && cursor.y <= 484)
                        restart();
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
    }

    void reload() {
        const double time = timeNow();
        const Cue cue = game.reload();
        feedback(cue, cursor, time);
        if (cue == Cue::reload)
            record("reload_begin", frame, game.generation, time);
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
        if (game.paused || !game.pending.empty()) {
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
        const int desired = std::min({sound.localFrame(time), game.scene->image.frames - 1, frame + 1});
        if (desired > frame) {
            frame = desired;
            upload(frame);
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
            const auto &dest = w->kind == Kind::target && game.hp > 1 ? node.flinch : w->onHit;
            media.prepare(dest, encounter.entrance(*game.scene, dest, frame));
            return;
        }
        for (const auto &next : game.scene->windows)
            if (next.begin > frame && game.active(&next)) {
                const auto &node = encounter.nodes[next.node];
                const auto &dest = next.kind == Kind::target && game.hp > 1 ? node.flinch : next.onHit;
                media.prepare(dest, encounter.entrance(*game.scene, dest, next.begin));
                return;
            }
        media.prepare(game.scene->image.next);
    }

    void drawHud() {
        const float right = float(encounter.width) - 38;
        ink.box(28, 24, 358, 70, {13, 19, 26, 217});
        ink.text(47, 35, 17, encounter.location, ivory);
        for (int n = 0; n < game.rules.lives; ++n)
            ink.star({54. + (game.rules.lives > 3 ? 18 : 24) * n, 73}, 7,
                     n < game.lives ? gold : SDL_Color{111, 91, 82, 245});
        for (int n = 0; n < 8; ++n)
            ink.box(150.f + n * 15.f, 68, 9, 11, n < game.arrows ? ivory : SDL_Color{104, 102, 95, 220});
        ink.text(287, 62, 15, game.reloadLeft > 0 ? "换匣中" : "符箭", gold);
        ink.box(right - 251, 24, 251, 70, {13, 19, 26, 217});
        ink.text(right - 234, 34, 17, progressLabel(), ivory);
        ink.text(right - 97, 34, 17, std::to_string(game.score) + " 分", ivory);
        ink.box(right - 234, 70, 126, 5, {85, 75, 65, 235});
        ink.box(right - 234, 70, 126.f * game.energy / game.rules.charge, 5, gold);
        ink.text(right - 95, 60, 16, game.energy == game.rules.charge ? "空格 雷符" : "雷符", gold);

        if (game.progress < int(encounter.nodes.size())) {
            const Window *target = game.scene->window(frame);
            std::string help = encounter.nodes[game.progress].label;
            if (game.active(target) && game.scene->impact > frame && frame >= game.scene->warning) {
                const Point p = game.scene->center(frame);
                if (p.x >= 0)
                    ink.ring(
                        p, (target->kind == Kind::projectile ? 17 : 20) + (game.scene->impact - frame) / 2,
                        {250, 156, 117, 148});
            }
            if (game.active(target) && target->kind == Kind::projectile)
                help = "拦截青火球";
            else if (game.active(target) && target->kind == Kind::civilian)
                help = "百姓经过  ·  收弩";
            else if (encounter.nodes[game.progress].hp > 1)
                help += "  ·  还需 " + std::to_string(game.hp) + " 次";
            ink.box(encounter.width / 2.f - 160, encounter.height - 61.f, 320, 35, {13, 19, 26, 184});
            ink.text(encounter.width / 2.f, encounter.height - 56.f, 18, help, ivory, true);
        }
        for (const auto &effect : effects)
            drawEffect(effect, visualTime - effect.start);
        if (cursor.x >= 0 && cursor.x < encounter.width && cursor.y >= 0 && cursor.y < encounter.height) {
            const float x = float(cursor.x), y = float(cursor.y);
            ink.ring(cursor, 8, {247, 230, 189, 198});
            ink.line(x - 13, y, x - 5, y, ivory);
            ink.line(x + 5, y, x + 13, y, ivory);
            ink.line(x, y - 13, x, y - 5, ivory);
            ink.line(x, y + 5, x, y + 13, ivory);
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
        return "净化 " + std::to_string(game.progress) + " / " + std::to_string(encounter.nodes.size());
    }

    void drawMenu() {
        auto screen = game.screen;
        ink.box(0, 0, float(encounter.width), float(encounter.height), {7, 11, 21, 124});
        ink.box(47, 137, 542, game.paused ? 430.f : 391.f, {12, 18, 29, 225});
        ink.box(70, 182, 45, 2, gold);
        ink.text(130, 169, 18, encounter.location, gold);
        std::string title = screen == Screen::title    ? encounter.title
                            : screen == Screen::failed ? "灯火未平"
                                                       : encounter.cleared;
        if (game.paused)
            title = "巡街暂停";
        ink.text(68, 215, 59, title, ivory);
        std::string detail = screen == Screen::title
                                 ? encounter.briefing
                                 : progressLabel() + "     得分 " + std::to_string(game.score);
        if (game.paused)
            detail = "恢复后从当前镜头继续。";
        ink.text(72, 313, 21, detail, ivory);
        ink.text(72, 360, 17, "左键施符  /  右键换匣  /  空格雷符", gold);
        if (encounter.selectableDifficulty && screen == Screen::title)
            ink.text(72, 386, 16, "难度 " + game.rules.label + "   ·   1 简单   2 普通   3 困难", ivory);
        ink.box(68, 414, 320, 54, {212, 161, 81, 245});
        ink.text(228, 426, 24,
                 game.paused               ? "继续巡街"
                 : screen == Screen::title ? "开始巡街"
                                           : "重新巡街",
                 {25, 22, 20, 255}, true);
        if (game.paused)
            ink.text(228, 502, 18, "返回标题", ivory, true);
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
        SDL_FRect video{0, 0, float(encounter.width), float(encounter.height)};
        if (streetTexture)
            check(SDL_RenderTexture(renderer, streetTexture.get(), nullptr, &video));
        check(SDL_RenderTexture(renderer, texture.get(), nullptr, &video));
        if (gunMode)
            drawGunBorder(ink);
        if (game.screen == Screen::play && frame >= 0 && game.scene)
            drawHud();
        if (game.screen != Screen::play || game.paused)
            drawMenu();

        if (!evidence.empty()) {
            if (!attempts && captureFrame == 0 && !fs::exists(evidence / "title.bmp"))
                saveFrame(evidence / "title.bmp");
            if (game.screen == Screen::complete && !fs::exists(evidence / "completed.bmp"))
                saveFrame(evidence / "completed.bmp");
            if (capture && now >= captureNext) {
                std::ostringstream name;
                name << std::setw(5) << std::setfill('0') << captureFrame++ << ".bmp";
                saveFrame(evidence / "frames" / name.str());
                samples.push_back({{"capture", captureFrame - 1},
                                   {"time", now - begun},
                                   {"street", streetFrame},
                                   {"frame", frame},
                                   {"clip", game.scene ? game.scene->image.id : ""},
                                   {"paused", game.paused},
                                   {"visual_time", visualTime},
                                   {"effects", effects.size()},
                                   {"run", attempts}});
                captureNext = now + 1. / 24;
            }
        }
        CampaignRecording::frame(renderer);
        check(SDL_RenderPresent(renderer));
        const auto ns = SDL_GetTicksNS();
        const double t = ns / 1e9;
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
            visible = {ns, game.generation, frame, game.scene};
            history.push_back(visible);
            while (ns - history.front().submitted > 300000000)
                history.pop_front();
            const auto *w = game.scene->window(frame);
            if (!game.paused && game.active(w) && w->kind == Kind::target && intervalFor[w->node] != -1) {
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
        if (game.screen == Screen::failed) {
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
        if (!game.interactive() || frame < 0 || game.reloadLeft)
            return;
        const Scene &s = *game.scene;
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
        const bool good =
            game.screen == Screen::complete && game.progress == int(encounter.nodes.size()) &&
            (!encounter.street || (encounter.selectableDifficulty && scenario != "street-hold") ||
             (streetFrame == encounter.street->frames - 1 && !streetMovie)) &&
            (!intercept || (game.blocks == 1 && game.hurts == 0 && game.launches == 1)) &&
            (scenario != "impact" || (game.blocks == 0 && game.hurts == 1 && attemptedImpact)) &&
            (scenario != "recovery" || (attempts >= 3 && titleResident == 0)) &&
            (scenario != "street-hold" || (encounter.street && game.hurts == 2 && game.lives == 1)) &&
            (scenario != "fx-reload" || (effectFinishedDuringReload && game.reloads == 1)) &&
            (scenario != "civilian-hit" || game.civilianHits > 0) &&
            (scenario != "charge" ||
             (game.blocks > 0 && game.hurts == 0 && game.hits == ordinaryHits + game.blocks - 2)) &&
            (!scenario.starts_with("thunder") || game.hits == ordinaryHits - 2);
        Json payload = {{"ok", good},
                        {"scenario", scenario},
                        {"difficulty", game.rules.id},
                        {"civilian_hits", game.civilianHits},
                        {"best_combo", game.bestCombo},
                        {"score", game.score},
                        {"renderer", SDL_GetRendererName(renderer)},
                        {"audio_device", sound.available()},
                        {"seconds", timeNow() - begun},
                        {"play_seconds", completedAt - playStarted},
                        {"shots", game.shots},
                        {"hits", game.hits},
                        {"lives", game.lives},
                        {"hurts", game.hurts},
                        {"launches", game.launches},
                        {"intercepts", game.blocks},
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
                        {"title_resident_movies", titleResident},
                        {"feedback_submit_ms", submits},
                        {"intervals", intervals},
                        {"transitions", transitions},
                        {"events", trace}};
        std::ofstream(evidence / "playthrough.json") << payload.dump(2) << '\n';
        if (!good)
            throw std::runtime_error("Replay assertions failed: " + scenario);
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
                visualTime += std::clamp(tick - visualTick, 0., 1. / 24);
            visualTick = tick;
            std::erase_if(effects, [&](const VisualCue &cue) {
                if (visualTime - cue.start < .45)
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
                const Cue cue = game.present(visible.generation, visible.frame);
                if (game.launches != before)
                    record("launch", visible.frame, visible.generation, now);
                if (cue != Cue::none) {
                    record(cueName(cue), visible.frame, visible.generation, now);
                    feedback(cue, {}, now);
                }
            }
            if (const Cue cue = game.tick(std::min(.06, now - previousTick), now); cue != Cue::none) {
                record(cueName(cue), frame, game.generation, now);
                feedback(cue, cursor, now);
            }
            previousTick = now;
            sync(now);
            scoreAudio.update(game.screen == Screen::play && !game.paused);
            syncStreet();
            render(timeNow());
            warmNext();
            if (!evidence.empty()) {
                totalMoviesPeak = std::max(totalMoviesPeak, media.count() + int(bool(streetMovie)));
                payloadPeak = std::max(payloadPeak, media.payloadBytes() +
                                                        (streetMovie ? streetMovie->payloadBytes() : 0));
                PROCESS_MEMORY_COUNTERS counter{};
                if (GetProcessMemoryInfo(GetCurrentProcess(), &counter, sizeof(counter)))
                    processPeak = std::max(processPeak, counter.PeakWorkingSetSize);
                // BMP readback and disk writes are synchronous during a recorded replay.
                const bool extendedTimeout = capture || CampaignRecording::enabled() ||
                                             scenario == "charge" || scenario == "recovery";
                if (now - begun > (extendedTimeout ? 180. : 55.))
                    throw std::runtime_error("Replay timed out: " + scenario);
                drive(timeNow());
            }
            SDL_Delay(1);
        }
        if (capture && !evidence.empty())
            sound.finishCapture(evidence, begun);
        report();
    }
};
void runCampaign(SDL_Window *window, SDL_Renderer *renderer, const fs::path &root, const std::string &name,
                 const fs::path &evidence, const std::string &difficultyId, bool gunMode,
                 const std::string &scenario, bool capture) {
    std::optional<CampaignRecording> recording;
    if (capture) {
        if (evidence.empty())
            throw std::runtime_error("Campaign capture requires --smoke <directory>");
        recording.emplace(evidence / "recording");
    }
    Campaign campaign(root, name);
    fs::path save;
    if (evidence.empty()) {
        std::unique_ptr<char, decltype(&SDL_free)> dir(SDL_GetPrefPath("Changan", "Lanterns"), SDL_free);
        if (!dir)
            throw std::runtime_error(SDL_GetError());
        save = fs::path(reinterpret_cast<const char8_t *>(dir.get())) / (name + ".json");
    } else {
        save = evidence / "checkpoint.json";
    }
    Progress state = Progress::load(save);
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
    const auto audioFolder = root / "assets/changan/audio";
    score.open(campaignDevice.device(), audioFolder);
    Json timeline = Json::array();
    const auto begun = timeNow();
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
        auto choice =
            campaignMenu(renderer, campaign, state, gun, !evidence.empty(), hasTitle ? &score : nullptr);
        menuAudio.reset();
        score.update(false);
        if (evidence.empty() && choice != MenuChoice::newGame)
            state.save(save);
        if (choice == MenuChoice::quit)
            break;
        if (choice == MenuChoice::newGame) {
            state.scores.clear();
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
            int completedReloads = 0;
            const auto opened = timeNow();
            ScoreAudio *music = nullptr;
            if (!stage.music.empty() && stage.level.empty()) {
                score.selectTrack(audioFolder / "music" / (stage.music + ".wav"));
                music = &score;
            } else {
                score.update(false);
            }
            if (!stage.trial.is_null()) {
                if (playTrial(window, renderer, root, stage, state, gun, !evidence.empty(), evidence,
                              scenario, music, completedReloads) == FilmEnd::quit) {
                    quit = true;
                    break;
                }
            } else if (stage.level.empty()) {
                for (auto film : stage.films) {
                    film.autoSkip = scenario == "skip-cg";
                    auto end = playFilm(window, renderer, root / "assets/changan/drama", film,
                                        state.subtitles, gun, !evidence.empty(), nullptr, music,
                                        state.voiceVolume / 100.f, state.effectsVolume / 100.f,
                                        {&state.arrows, &state.reloadRemaining,
                                         difficulty(state.difficulty).reloadSeconds, &completedReloads});
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
                Encounter level(root / "worlds/changan" / stage.level);
                App fight(window, renderer, root / "assets/changan" / stage.level, std::move(level),
                          evidence.empty() ? fs::path{} : evidence / stage.id, "normal", false, gun);
                fight.game.rules = difficulty(state.difficulty);
                fight.campaignFight = true;
                if (!stage.music.empty()) {
                    if (!fight.encounter.selectableDifficulty)
                        fight.scoreAudio.open(fight.sound.device(), audioFolder);
                    fight.scoreAudio.selectTrack(audioFolder / "music" / (stage.music + ".wav"));
                }
                fight.scoreAudio.volume(state.musicVolume / 100.f, state.effectsVolume / 100.f);
                fight.startingLives = std::clamp(state.lives, 1, fight.game.rules.lives);
                fight.startingEnergy = std::clamp(state.energy, 0, fight.game.rules.charge);
                fight.startingArrows = state.arrows;
                fight.startingReload = state.reloadRemaining;
                SDL_HideCursor();
                fight.run();
                SDL_ShowCursor();
                if (fight.game.screen != Screen::complete) {
                    quit = !fight.returnToMenu;
                    break;
                }
                auto &g = fight.game;
                completedReloads = g.reloads;
                state.scores[stage.chapter].add({g.score, g.hits, g.shots, g.bestCombo,
                                                 g.hurts + g.civilianHits * g.rules.civilianDamage,
                                                 g.progress});
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
                std::ofstream(evidence / "timeline.json") << timeline.dump(2) << '\n';
            }
            if (n + 1 == campaign.stages.size() || campaign.stages[n + 1].chapter != stage.chapter) {
                if (!chapterResults(renderer, stage, state.scores[stage.chapter], gun, !evidence.empty(),
                                    music)) {
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
    fs::path root, out;
    std::string scenario = "normal", levelId, campaignId, difficultyId = "normal";
    bool capture = false, gunMode = false;
    for (int i = 1; i < argc; ++i) {
        const std::wstring arg = argv[i];
        if (arg == L"--root" && i + 1 < argc)
            root = fs::absolute(argv[++i]);
        else if (arg == L"--smoke" && i + 1 < argc)
            out = fs::absolute(argv[++i]);
        else if (arg == L"--difficulty" && i + 1 < argc) {
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
        check(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO));
        if (root.empty())
            root = fs::path(reinterpret_cast<const char8_t *>(SDL_GetBasePath()));
        if (levelId.empty() && campaignId.empty()) {
            std::ifstream manifest(root / "worlds/changan/start.json");
            const Json start = manifest ? Json::parse(manifest) : Json{{"level", "m0"}};
            levelId = start.value("level", "");
            campaignId = start.value("campaign", "");
        }
        if (campaignId.empty() &&
            (levelId.empty() ||
             levelId.find_first_not_of("0123456789abcdefghijklmnopqrstuvwxyz_") != std::string::npos))
            throw std::runtime_error("Invalid encounter name");
        std::optional<Encounter> sizing;
        if (campaignId.empty())
            sizing.emplace(root / "worlds/changan" / levelId);
        SDL_SetHint(SDL_HINT_RENDER_VSYNC, "1");
        std::unique_ptr<SDL_Window, decltype(&SDL_DestroyWindow)> w(
            SDL_CreateWindow("长安灯妖录", 1280, 720,
                             SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY |
                                 (out.empty() ? 0 : SDL_WINDOW_HIDDEN)),
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
            runCampaign(w.get(), r.get(), root, campaignId, out, difficultyId, gunMode, scenario, capture);
        } else {
            App app(w.get(), r.get(), root / "assets/changan" / levelId, std::move(*sizing), out, scenario,
                    capture);
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
            SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "长安灯妖录", error.what(), nullptr);
        }
        SDL_Quit();
        return 1;
    }
    SDL_Quit();
    return 0;
}
