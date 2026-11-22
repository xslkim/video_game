#include "tvgun.hpp"
#include "sound.hpp"
#include "ui.hpp"
#include <SDL3/SDL_main.h>
#include <windows.h>
#include <bcrypt.h>
#include <deque>
#include <iostream>
#include <iomanip>
#include <sstream>

namespace dc {
static void ensure(bool ok) {
    if (!ok)
        throw std::runtime_error(SDL_GetError());
}
static std::string digest(const fs::path &p) {
    std::ifstream in(p, std::ios::binary);
    if (!in)
        throw std::runtime_error("Missing movie: " + p.filename().string());
    std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(in)), {});
    unsigned char hash[32]{};
    if (BCryptHash(BCRYPT_SHA256_ALG_HANDLE, nullptr, 0, bytes.data(), ULONG(bytes.size()), hash, 32) !=
        0)
        throw std::runtime_error("SHA256 failed");
    std::ostringstream os;
    for (auto x : hash)
        os << std::hex << std::setw(2) << std::setfill('0') << int(x);
    return os.str();
}
static double now() { return SDL_GetTicksNS() / 1e9; }
struct Stamp {
    uint64_t ns;
    int generation, frame;
    Layout layout;
};
struct Session {
    SDL_Window *w;
    SDL_Renderer *r;
    Level level;
    Game g;
    Ink ink;
    Sound sound;
    Receiver net;
    std::map<std::string, std::unique_ptr<Movie>> media;
    SDL_Texture *currentTex = nullptr;
    SDL_Texture *previousTex = nullptr;
    int generation = -1, frame = -1, fade = 0, fadeFrames = 2;
    bool tv = false, subs = true, running = true, dev = false;
    std::string notice;
    Point cursor{-20, -20};
    Point impact{};
    double impactUntil = 0;
    bool impactHit = false;
    std::deque<Stamp> displayed;
    fs::path evidence;
    bool automated = false;
    int autoShot = -1;
    double lastTick = 0, buttonTime = 0;
    std::vector<double> latency, feedbackLatency;
    bool pendingHit = false, pendingFeedback = false;
    std::string scenario = "normal";
    bool resumed = false, scared = false, pausedOnce = false;
    bool civilMistake = false;
    int tutorialRound = 0;
    std::vector<std::string> path;
    Session(SDL_Window *window, SDL_Renderer *renderer, const fs::path &root, const fs::path &logdir)
        : w(window), r(renderer), level(root / "worlds/western/opening"), g(level), ink{renderer},
          evidence(logdir), automated(!logdir.empty()) {
        for (auto &[id, clip] : level.clips) {
            auto path = root / "assets/western/opening_slices" / (id + ".mp4");
            if (digest(path) != clip.hash)
                throw std::runtime_error("Movie hash mismatch: " + id);
            media[id] = std::make_unique<Movie>(path, clip.frames);
            media[id]->at(clip.start);
        }
        for (auto **t : {&currentTex, &previousTex}) {
            *t = SDL_CreateTexture(r, SDL_PIXELFORMAT_IYUV, SDL_TEXTUREACCESS_STREAMING, 1280, 720);
            ensure(*t != nullptr);
            SDL_SetTextureBlendMode(*t, SDL_BLENDMODE_BLEND);
        }
        SDL_SetRenderDrawBlendMode(r, SDL_BLENDMODE_BLEND);
        if (automated)
            fs::create_directories(evidence);
    }
    ~Session() {
        SDL_DestroyTexture(currentTex);
        SDL_DestroyTexture(previousTex);
    }
    void toggleTv() {
        if (tv) {
            net.close();
            tv = false;
            notice.clear();
        } else if (net.open()) {
            tv = true;
            notice = "TVGun 已监听 · 等待手机定位";
        } else
            notice = "端口 9000 或 8001 正被占用";
        displayed.clear();
    }
    void home() {
        g.screen = Screen::title;
        g.paused = false;
        sound.pause(true, now());
        generation = -1;
        displayed.clear();
        pendingHit = false;
    }
    void begin(bool checkpoint = false) {
        g.start(checkpoint);
        displayed.clear();
        pendingHit = false;
        if (tv && !net.hasLock())
            g.paused = true;
    }
    void pause() {
        if (g.screen != Screen::play)
            return;
        if (g.paused && tv && !net.hasLock())
            return;
        g.paused = !g.paused;
        displayed.clear();
        sound.pause(g.paused, now());
    }
    void activate(Point p, uint64_t ns) {
        if (g.screen != Screen::play || g.paused) {
            if (p.y < 455 || p.y > 503)
                return;
            if (p.x >= 70 && p.x <= 295) {
                if (g.screen == Screen::title || g.screen == Screen::complete)
                    begin();
                else if (g.screen == Screen::failed)
                    begin(true);
                else
                    pause();
            } else if (p.x >= 308 && p.x <= 493) {
                if (g.screen == Screen::title)
                    toggleTv();
                else if (g.screen == Screen::failed)
                    begin();
                else
                    home();
            }
            return;
        }
        auto it = std::find_if(displayed.rbegin(), displayed.rend(),
                               [&](const Stamp &s) { return s.ns <= ns; });
        if (it == displayed.rend() || ns - it->ns > 300000000 || it->generation != g.generation)
            return;
        auto point = it->layout.toVideo(p);
        if (point.x < 0 || point.x >= 1280 || point.y < 0 || point.y >= 720)
            return;
        const int before = g.shots;
        g.shoot(point, it->generation, it->frame);
        if (before != g.shots || g.feedback == Feedback::empty) {
            if (before != g.shots) {
                impact = p;
                impactHit = g.feedback == Feedback::hit || g.feedback == Feedback::rescue;
                impactUntil = now() + .16;
            }
            sound.cue(g.feedback);
            buttonTime = ns / 1e9;
            pendingFeedback = true;
            if (before != g.shots && it->generation != g.generation)
                pendingHit = true;
        }
    }
    void remote(RemoteAction act, Point p) {
        Point screen{p.x * 1280 / 1920, p.y * 720 / 1080};
        if (act == RemoteAction::aim) {
            cursor = screen;
            return;
        }
        if (act == RemoteAction::lost) {
            if (g.screen == Screen::play && !g.paused)
                pause();
            cursor = {-20, -20};
            return;
        }
        if (act == RemoteAction::exit) {
            if (g.screen == Screen::play) {
                if (!g.paused)
                    pause();
            } else
                home();
            return;
        }
        if (act == RemoteAction::start) {
            if (g.screen == Screen::title || g.screen == Screen::complete)
                begin();
            else if (g.screen == Screen::failed)
                begin(true);
            else if (g.paused)
                pause();
        } else if (act == RemoteAction::reload) {
            g.reload();
            if (g.reloadTime == .5)
                sound.cue(Feedback::reload);
        } else if (act == RemoteAction::shoot) {
            if (p.x < 0 || p.y < 0 || p.x >= 1920 || p.y >= 1080) {
                g.reload();
                return;
            }
            activate(screen, SDL_GetTicksNS());
        }
    }
    void events() {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT)
                running = false;
            if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && !automated && g.interactive())
                pause();
            if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {
                switch (e.key.key) {
                case SDLK_ESCAPE:
                    if (g.screen == Screen::play)
                        pause();
                    else
                        home();
                    break;
                case SDLK_RETURN:
                    if (g.screen != Screen::play)
                        begin(g.screen == Screen::failed);
                    else if (g.paused)
                        pause();
                    break;
                case SDLK_SPACE:
                    g.skip();
                    break;
                case SDLK_R:
                    g.reload();
                    break;
                case SDLK_C:
                    subs = !subs;
                    break;
                case SDLK_F2:
                    if (g.screen == Screen::title)
                        toggleTv();
                    break;
                case SDLK_F3:
                    dev = !dev;
                    break;
                case SDLK_F11:
                    SDL_SetWindowFullscreen(w, !(SDL_GetWindowFlags(w) & SDL_WINDOW_FULLSCREEN));
                    break;
                }
            }
            if (e.type == SDL_EVENT_MOUSE_MOTION && (!tv || g.screen != Screen::play)) {
                float x, y;
                SDL_RenderCoordinatesFromWindow(r, e.motion.x, e.motion.y, &x, &y);
                cursor = {x, y};
            }
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && (!tv || g.screen != Screen::play || g.paused)) {
                float x, y;
                SDL_RenderCoordinatesFromWindow(r, e.button.x, e.button.y, &x, &y);
                if (e.button.button == SDL_BUTTON_LEFT)
                    activate({x, y}, e.button.timestamp);
                else if (e.button.button == SDL_BUTTON_RIGHT) {
                    g.reload();
                    if (g.reloadTime == .5)
                        sound.cue(Feedback::reload);
                }
            }
        }
        if (tv)
            net.poll(SDL_GetTicks(), [&](auto a, auto p) { remote(a, p); });
    }
    void picture(Movie &movie, int f) {
        auto *img = movie.at(f);
        ensure(SDL_UpdateYUVTexture(currentTex, nullptr, img->data[0], img->linesize[0], img->data[1],
                                    img->linesize[1], img->data[2], img->linesize[2]));
    }
    void screenshot(const std::string &name) {
        auto *surface = SDL_RenderReadPixels(r, nullptr);
        if (surface) {
            auto dest = (evidence / (name + ".bmp")).u8string();
            SDL_SaveBMP(surface, reinterpret_cast<const char *>(dest.c_str()));
            SDL_DestroySurface(surface);
        }
    }
    void render() {
        double t = now();
        g.tick(std::clamp(t - lastTick, 0., .1));
        lastTick = t;
        if (g.screen == Screen::play && generation == g.generation) {
            int before = g.injuries;
            auto was = g.feedback;
            if (!g.paused)
                g.present(sound.localFrame(t));
            if (g.injuries != before)
                sound.cue(Feedback::hurt);
            if (was != Feedback::bonus && g.feedback == Feedback::bonus)
                sound.cue(Feedback::bonus);
        }
        double shake = (g.feedback == Feedback::hurt && g.feedbackTime > .43)
                           ? 2.5 * std::sin(g.feedbackTime * 85)
                           : 0;
        Layout layout(tv, shake);
        if (g.screen == Screen::title) {
            if (generation != -2) {
                picture(*media.at("A0_travel_main"), 0);
                generation = -2;
                frame = 0;
                fade = 0;
            }
        } else if (g.screen == Screen::play) {
            if (generation != g.generation) {
                if (automated) {
                    path.push_back(g.clip->id);
                    if (g.clip->id == "A1_threat_wagon")
                        ++tutorialRound;
                }
                std::swap(currentTex, previousTex);
                fade = generation >= 0 ? fadeFrames : 0;
                sound.begin(*media.at(g.clip->id), g.frame, g.speed(), t);
                if (g.paused)
                    sound.pause(true, t);
                generation = g.generation;
                frame = -1;
                displayed.clear();
                net.fence();
            }
            if (frame != g.frame) {
                picture(*media.at(g.clip->id), g.frame);
                frame = g.frame;
            }
        } else if (generation != g.generation) {
            picture(*media.at(g.clip->id), g.clip->frames - 1);
            generation = g.generation;
            sound.pause(true, t);
            displayed.clear();
            fade = 0;
        }
        SDL_SetRenderDrawColor(r, 14, 15, 14, 255);
        SDL_RenderClear(r);
        SDL_Rect area{int(std::round(layout.video.x)), int(layout.video.y),
                      int(std::round(layout.video.w)), int(layout.video.h)};
        SDL_SetRenderClipRect(r, &area);
        SDL_SetTextureAlphaMod(currentTex, 255);
        SDL_RenderTexture(r, currentTex, nullptr, &layout.picture);
        if (fade > 0) {
            SDL_SetTextureAlphaMod(previousTex, Uint8(175 * fade / std::max(1, fadeFrames)));
            SDL_RenderTexture(r, previousTex, nullptr, &layout.picture);
            --fade;
        }
        SDL_SetRenderClipRect(r, nullptr);
        drawUI(ink, g, layout, cursor, tv, net.hasLock(), subs, notice);
        if (dev && g.screen == Screen::play) {
            if (!g.clip->masks.empty())
                for (auto s : g.clip->masks.at(g.frame)) {
                    auto p = layout.fromVideo({s.x0 * 2., s.y * 2.});
                    ink.box(float(p.x), float(p.y), float((s.x1 - s.x0) * 2 * layout.picture.w / 1280),
                            float(2 * layout.picture.h / 720), {30, 244, 140, 98});
                }
            ink.box(30, 80, 370, 30, dark);
            ink.text(39, 82, 16,
                     g.clip->id + "   f " + std::to_string(g.frame) + " / " +
                         std::to_string(g.clip->frames - 1),
                     ivory);
        }
        if (g.interactive() && t < impactUntil) {
            int radius = 6 + int((.16 - (impactUntil - t)) * 95);
            ink.ring(impact, radius, impactHit ? gold : ivory);
        }
        if (tv && net.hasLock() && (g.screen != Screen::play || g.paused))
            ink.ring(cursor, 10, gold);
        if (tv) {
            SDL_Color white{255, 255, 255, 255};
            ink.box(0, 0, 1280, 16, white);
            ink.box(0, 704, 1280, 16, white);
            ink.box(0, 16, 16, 688, white);
            ink.box(1264, 16, 16, 688, white);
        }
        if (g.screen != Screen::play || g.paused)
            SDL_ShowCursor();
        else
            SDL_HideCursor();
        if (automated && (g.screen == Screen::complete || (g.screen == Screen::title && path.empty())))
            screenshot(g.screen == Screen::complete ? "completed" : "title");
        if (automated && g.screen == Screen::play && g.clip->id == "A4_threat_porch" && frame == 25 &&
            !fs::exists(evidence / "saloon.bmp"))
            screenshot("saloon");
        SDL_RenderPresent(r);
        if (g.interactive()) {
            uint64_t ns = SDL_GetTicksNS();
            displayed.push_back({ns, g.generation, g.frame, layout});
            while (!displayed.empty() && ns - displayed.front().ns > 300000000)
                displayed.pop_front();
            if (pendingHit) {
                latency.push_back(1000 * (ns / 1e9 - buttonTime));
                pendingHit = false;
            }
            if (pendingFeedback) {
                feedbackLatency.push_back(1000 * (ns / 1e9 - buttonTime));
                pendingFeedback = false;
            }
        }
    }
    void pressAt(Point p, Uint8 button = SDL_BUTTON_LEFT) {
        if (displayed.empty())
            return;
        p = displayed.back().layout.fromVideo(p);
        SDL_Event e{};
        e.type = SDL_EVENT_MOUSE_BUTTON_DOWN;
        e.button.button = button;
        e.button.timestamp = SDL_GetTicksNS();
        SDL_RenderCoordinatesToWindow(r, float(p.x), float(p.y), &e.button.x, &e.button.y);
        SDL_PushEvent(&e);
    }
    void autoplay() {
        if (g.screen == Screen::title) {
            begin();
            return;
        }
        if (scenario == "recovery") {
            if (g.screen == Screen::failed && !resumed) {
                screenshot("failed");
                resumed = true;
                begin(true);
                return;
            }
            if (g.paused) {
                pause();
                return;
            }
            if (g.screen == Screen::play) {
                if (g.clip->id.starts_with("A0_mayor")) {
                    g.skip();
                    return;
                }
                if (!pausedOnce && g.clip->id == "A0_travel_main" && g.frame > 4) {
                    pausedOnce = true;
                    pause();
                    return;
                }
                if (g.clip->id == "A1_threat_wagon" && tutorialRound == 1) {
                    if (g.enabled(g.frame) && g.shots < 6)
                        pressAt({32, 32});
                    else if (!g.ammo && !g.reloadTime)
                        pressAt({}, SDL_BUTTON_RIGHT);
                    return;
                }
                if (g.clip->civilian && !civilMistake && g.frame == 36) {
                    auto &spans = g.clip->masks[g.frame];
                    if (!spans.empty()) {
                        auto s = spans[spans.size() / 2];
                        pressAt({double(s.x0 + s.x1), s.y * 2. + 1});
                        civilMistake = true;
                    }
                    return;
                }
                if (g.clip->id == "A4_threat_porch" && (!resumed || !scared) && g.enabled(g.frame)) {
                    pressAt(level.protect);
                    if (resumed)
                        scared = true;
                    return;
                }
                if (g.ammo == 0 && !g.reloadTime) {
                    pressAt({}, SDL_BUTTON_RIGHT);
                    return;
                }
            }
        }
        if (g.screen == Screen::complete || g.screen == Screen::failed) {
            running = false;
            return;
        }
        if (!g.interactive() || !g.enabled(g.frame) || autoShot == g.generation)
            return;
        if (scenario != "early" && (g.clip->expires < 0 || g.frame < g.clip->expires - 5))
            return;
        // Exercise the same window-coordinate input and displayed-frame lookup as a mouse.
        Point p = g.clip->beat == "porch" ? level.rescue : g.clip->point;
        if (g.clip->beat != "porch" && !g.clip->covers(g.frame, p)) {
            auto &spans = g.clip->masks.at(g.frame);
            auto it = std::max_element(spans.begin(), spans.end(),
                                       [](auto a, auto b) { return a.x1 - a.x0 < b.x1 - b.x0; });
            if (it == spans.end())
                throw std::runtime_error("Smoke test found empty interaction mask");
            p = {double(it->x0 + it->x1), it->y * 2. + 1};
        }
        autoShot = g.generation;
        pressAt(p);
    }
    void run() {
        lastTick = now();
        double started = lastTick;
        while (running) {
            events();
            render();
            if (automated) {
                autoplay();
                if (now() - started > 110)
                    throw std::runtime_error("Timed smoke run stalled");
            }
            SDL_Delay(2);
        }
        if (automated) {
            Json report = {{"scenario", scenario},
                           {"path", path},
                           {"hits", g.hits},
                           {"lives", g.lives},
                           {"shots", g.shots},
                           {"seconds", now() - started},
                           {"branch_submit_ms", latency},
                           {"feedback_submit_ms", feedbackLatency},
                           {"renderer", SDL_GetRendererName(r)},
                           {"audio_device", sound.available()}};
            std::ofstream(evidence / "playthrough.json") << report.dump(2);
            bool ok = scenario == "recovery"
                          ? (resumed && scared && civilMistake && tutorialRound >= 2 && g.hits == 1)
                          : g.hits == 6;
            if (g.screen != Screen::complete || !ok || !g.lives)
                throw std::runtime_error("Playthrough failed");
        }
    }
};
} // namespace dc
int wmain(int argc, wchar_t **argv) {
    using namespace dc;
    fs::path root, evidence;
    bool tv = false;
    int fade = 2;
    std::string scenario = "normal";
    for (int i = 1; i < argc; ++i) {
        std::wstring a = argv[i];
        if (a == L"--root" && i + 1 < argc)
            root = fs::absolute(argv[++i]);
        else if (a == L"--smoke" && i + 1 < argc)
            evidence = fs::absolute(argv[++i]);
        else if (a == L"--tv")
            tv = true;
        else if (a == L"--cut")
            fade = 0;
        else if (a == L"--fade-one")
            fade = 1;
        else if (a == L"--early")
            scenario = "early";
        else if (a == L"--recovery")
            scenario = "recovery";
    }
    try {
        SDL_SetMainReady();
        ensure(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO));
        if (root.empty())
            root = fs::u8path(SDL_GetBasePath());
        SDL_SetHint(SDL_HINT_RENDER_VSYNC, "1");
        auto *w = SDL_CreateWindow("Dust Creek · 尘溪镇", 1280, 720,
                                   SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY |
                                       (evidence.empty() ? 0 : SDL_WINDOW_HIDDEN));
        ensure(w != nullptr);
        auto *r = SDL_CreateRenderer(w, "opengl");
        if (!r)
            r = SDL_CreateRenderer(w, nullptr);
        ensure(r != nullptr);
        ensure(SDL_SetRenderLogicalPresentation(r, 1280, 720, SDL_LOGICAL_PRESENTATION_LETTERBOX));
        {
            Session session(w, r, root, evidence);
            session.fadeFrames = fade;
            session.scenario = scenario;
            if (tv)
                session.toggleTv();
            session.run();
        }
        SDL_DestroyRenderer(r);
        SDL_DestroyWindow(w);
        SDL_Quit();
        return 0;
    } catch (const std::exception &e) {
        if (!evidence.empty()) {
            fs::create_directories(evidence);
            std::ofstream(evidence / "error.txt") << e.what();
        } else
            SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Dust Creek", e.what(), nullptr);
        std::cerr << e.what() << "\n";
        SDL_Quit();
        return 1;
    }
}
