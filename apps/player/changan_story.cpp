#include "changan_story.hpp"
#include "changan_record.hpp"
#include "gamepad_input.hpp"
#include "linyuan_feedback.hpp"
#include "sound.hpp"
#include "ui.hpp"
#include <deque>
#include <fstream>
#include <windows.h>

namespace ca {
using Texture = std::unique_ptr<SDL_Texture, decltype(&SDL_DestroyTexture)>;
namespace {
void checkVoice(const std::string &id) {
    const auto slash = id.find('/');
    if (slash == std::string::npos || slash == 0 || slash + 1 == id.size() ||
        id.find('/', slash + 1) != std::string::npos ||
        id.find_first_not_of("abcdefghijklmnopqrstuvwxyz_0123456789/") != std::string::npos)
        throw std::runtime_error("Invalid voice identifier: " + id);
}

Point closestOnEdge(Point p, Point a, Point b) {
    const double dx = b.x - a.x, dy = b.y - a.y;
    const double ratio =
        std::clamp(((p.x - a.x) * dx + (p.y - a.y) * dy) / std::max(1e-9, dx * dx + dy * dy), 0., 1.);
    return {a.x + ratio * dx, a.y + ratio * dy};
}

bool segmentsTouch(Point a, Point b, Point c, Point d) {
    const auto cross = [](Point u, Point v, Point w) {
        return (v.x - u.x) * (w.y - u.y) - (v.y - u.y) * (w.x - u.x);
    };
    const auto overlaps = [](double a0, double a1, double b0, double b1) {
        return std::max(std::min(a0, a1), std::min(b0, b1)) <= std::min(std::max(a0, a1), std::max(b0, b1));
    };
    return overlaps(a.x, b.x, c.x, d.x) && overlaps(a.y, b.y, c.y, d.y) &&
           cross(a, b, c) * cross(a, b, d) <= 0 && cross(c, d, a) * cross(c, d, b) <= 0;
}

bool guardBlocksAssist(const FilmChoice &choice, const TrackedRegion &target, int frame, Point aim) {
    if (!choice.protectAssist || choice.guards.empty())
        return false;
    const auto outline = target.outline(frame);
    Point nearest = aim;
    double best = 1e20;
    for (size_t i = 0; i < outline.size(); ++i) {
        const auto candidate = closestOnEdge(aim, outline[i], outline[(i + 1) % outline.size()]);
        const double distance = std::hypot(candidate.x - aim.x, candidate.y - aim.y);
        if (distance < best) {
            best = distance;
            nearest = candidate;
        }
    }
    for (const auto &guard : choice.regions) {
        if (frame < guard.begin || frame >= guard.end ||
            std::find(choice.guards.begin(), choice.guards.end(), guard.id) == choice.guards.end())
            continue;
        const auto shape = guard.outline(frame);
        for (size_t i = 0; i < shape.size(); ++i)
            if (segmentsTouch(aim, nearest, shape[i], shape[(i + 1) % shape.size()]))
                return true;
    }
    return false;
}

std::vector<DialogueCue> readDialogue(const Json &shot, int frames) {
    std::vector<DialogueCue> result;
    for (const auto &cue : shot.value("cues", Json::array())) {
        DialogueCue parsed{cue.at("begin"), cue.at("end"), cue.at("voice"), cue.at("subtitle")};
        checkVoice(parsed.voice);
        if (parsed.begin < 0 || parsed.end <= parsed.begin || parsed.end > frames ||
            (!result.empty() && result.back().end > parsed.begin))
            throw std::runtime_error("Invalid dialogue timing: " + parsed.voice);
        result.push_back(std::move(parsed));
    }
    return result;
}
void drawBossTrialHud(Ink &ink, int lives, int ammo, double reloadLeft, int phase, int done, int total,
                      bool canStrike) {
    ink.box(28, 22, 358, 66, {11, 18, 24, 220});
    ink.text(46, 32, 17, phase > 0 ? "临渊江 · 浅滩" : "九曲渡 · 对决", ivory);
    const int maxLives = lives > 3 ? 5 : 3;
    for (int n = 0; n < maxLives; ++n)
        ink.star({54. + (maxLives > 3 ? 18 : 24) * n, 68}, 7,
                 n < lives ? gold : SDL_Color{111, 91, 82, 245});
    for (int n = 0; n < 8; ++n)
        ink.box(150.f + n * 15.f, 63, 9, 11, n < ammo ? ivory : SDL_Color{104, 102, 95, 220});
    ink.text(287, 57, 15, reloadLeft > 0 ? "收剑中" : "飞剑", gold);
    if (phase > 0 && total > 0) {
        ink.box(410, 20, 460, 68, {11, 18, 24, 222});
        ink.box(410, 20, 460, 2, {218, 170, 84, 235});
        const char *phaseTitle = phase == 1   ? "一阶段 · 双肩琥珀罐"
                                 : phase == 2 ? "二阶段 · 迎击兽火"
                                              : "三阶段 · 破口内核心";
        ink.text(428, 28, 17, "凶兽 · 饕餮", gold);
        ink.text(852 - 170, 28, 16, phaseTitle, ivory);
        const int clampedTotal = std::max(1, total);
        const int clampedDone = std::clamp(done, 0, clampedTotal);
        const int remain = clampedTotal - clampedDone;
        const float barX = 428.f, barW = 424.f, gap = 6.f;
        const float cellW = (barW - gap * (clampedTotal - 1)) / clampedTotal;
        for (int k = 0; k < clampedTotal; ++k) {
            const SDL_Color fill =
                k < remain ? (phase == 3 ? SDL_Color{255, 118, 62, 245} : SDL_Color{245, 192, 72, 245})
                           : SDL_Color{55, 58, 62, 210};
            ink.box(barX + k * (cellW + gap), 58, cellW, 13, fill);
        }
    }
    if (canStrike || (ammo == 0 && reloadLeft <= 0)) {
        ink.box(982, 22, 266, 46, {11, 18, 24, 220});
        ink.box(982, 22, 4, 46, gold);
        ink.text(1115, 34, 18, canStrike ? "空格 / 中键 万剑归宗" : "剑匣已空 · 右键 / R 收剑", gold, true);
    }
}
} // namespace
void drawGunBorder(Ink &ink) {
    constexpr SDL_Color white{255, 255, 255, 255};
    constexpr SDL_Color band{8, 10, 12, 255};
    // The receiver advertises 24 white and 48 dark pixels in 1920 x 1080 coordinates.
    ink.box(16, 16, 1248, 32, band);
    ink.box(16, 672, 1248, 32, band);
    ink.box(16, 48, 32, 624, band);
    ink.box(1232, 48, 32, 624, band);
    ink.box(0, 0, 1280, 16, white);
    ink.box(0, 704, 1280, 16, white);
    ink.box(0, 16, 16, 688, white);
    ink.box(1264, 16, 16, 688, white);
}

std::vector<Point> TrackedRegion::outline(int frame) const {
    auto right = outlines.upper_bound(frame);
    if (right == outlines.begin())
        return right->second;
    const auto left = std::prev(right);
    if (right == outlines.end())
        return left->second;
    std::vector<Point> result = left->second;
    const double t = double(frame - left->first) / (right->first - left->first);
    for (size_t i = 0; i < result.size(); ++i) {
        result[i].x += t * (right->second[i].x - result[i].x);
        result[i].y += t * (right->second[i].y - result[i].y);
    }
    return result;
}

bool TrackedRegion::covers(int frame, Point p, double margin) const {
    if (frame < begin || frame >= end)
        return false;
    const auto poly = outline(frame);
    bool inside = false;
    for (size_t i = 0, j = poly.size() - 1; i < poly.size(); j = i++) {
        auto a = poly[i], b = poly[j];
        if (margin > 0) {
            const double dx = b.x - a.x, dy = b.y - a.y;
            const double t = std::clamp(
                ((p.x - a.x) * dx + (p.y - a.y) * dy) / std::max(1e-9, dx * dx + dy * dy), 0., 1.);
            if (std::hypot(p.x - a.x - t * dx, p.y - a.y - t * dy) <= margin)
                return true;
        }
        if ((a.y > p.y) != (b.y > p.y) && p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x)
            inside = !inside;
    }
    return inside;
}

FilmEnd playFilm(SDL_Window *window, SDL_Renderer *renderer, const fs::path &media, const Film &film,
                 bool subtitles, Receiver *receiver, bool automated, FilmChoice *choice, ScoreAudio *score,
                 float voiceGain, float effectsGain, TravelReload travel) {
    Movie movie(media / (film.take + ".mp4"), film.frames);
    Sound sound;
    sound.limitToWallClock(film.wallClockLimited);
    CampaignRecording::Audio recorded(sound, 60);
    ScoreAudio localFoley;
    if (!score && (choice || travel.arrows)) {
        localFoley.open(sound.device(), media.parent_path() / "audio", false);
        localFoley.volume(0.f, effectsGain);
    }
    ScoreAudio &foley = score ? *score : localFoley;
    std::unique_ptr<SDL_AudioStream, decltype(&SDL_DestroyAudioStream)> dialogue(nullptr,
                                                                                 SDL_DestroyAudioStream);
    auto say = [&](const std::string &id) {
        if (!sound.device())
            return;
        const auto file = (media.parent_path() / "audio/voice" / (id + ".wav")).u8string();
        SDL_AudioSpec format{};
        Uint8 *pcm = nullptr;
        Uint32 bytes = 0;
        if (!SDL_LoadWAV(reinterpret_cast<const char *>(file.c_str()), &format, &pcm, &bytes))
            throw std::runtime_error("Missing dialogue: " + id);
        std::unique_ptr<Uint8, decltype(&SDL_free)> owner(pcm, SDL_free);
        dialogue.reset(SDL_CreateAudioStream(&format, &format));
        if (!dialogue || !SDL_BindAudioStream(sound.device(), dialogue.get()) ||
            !SDL_SetAudioStreamGain(dialogue.get(), voiceGain) ||
            !SDL_PutAudioStreamData(dialogue.get(), pcm, bytes) || !SDL_FlushAudioStream(dialogue.get()))
            throw std::runtime_error(SDL_GetError());
    };
    const DialogueCue *speaking = nullptr;
    Ink ink(renderer);
    Texture texture(
        SDL_CreateTexture(renderer, SDL_PIXELFORMAT_IYUV, SDL_TEXTUREACCESS_STREAMING, 1280, 720),
        SDL_DestroyTexture);
    if (!texture)
        throw std::runtime_error(SDL_GetError());
    auto now = [] { return SDL_GetTicksNS() / 1e9; };
    int displayed = -1;
    const int filmEnd = film.endFrame > 0 ? std::min(film.endFrame, film.frames) : film.frames;
    const int filmStart = std::clamp(film.startFrame, 0, filmEnd - 1);
    Point aim{-1, -1};
    uint64_t submitted = 0;
    std::deque<std::pair<uint64_t, int>> history;
    bool paused = false;
    double pauseStart = 0;
    bool slowedWindow = false;
    bool sentEarly = false, sentLate = false, probePaused = false, probeResumed = false;
    bool skipSent = false;
    double localReload = 0, previous = now();
    double &reloadLeft = travel.remaining ? *travel.remaining : localReload;
    int *arrows = choice ? &choice->ammo : travel.arrows;
    double exposedLeft = 0;
    double effectTime = 0, effectAt = -1, windowOpenAt = -1;
    Point effectPoint{};
    GamepadController gamepad;
    sound.begin(movie, filmStart, 1., now());
    if (!film.voice.empty() && film.cues.empty())
        say(film.voice);
    sound.clipGain(film.take == "aying_help" ? voiceGain : effectsGain);
    auto pause = [&](bool yes) {
        if (paused == yes)
            return;
        if (yes)
            pauseStart = now();
        else if (travel.pausedSeconds)
            *travel.pausedSeconds += now() - pauseStart;
        paused = yes;
        sound.pause(yes, now());
    };
    for (;;) {
        bool skip = false;
        auto fire = [&](Point p, uint64_t when) {
            if (!choice || paused || choice->fired ||
                (!choice->story && (choice->ammo == 0 || reloadLeft > 0)))
                return;
            if (choice->closed >= 0 && when / 1e9 >= choice->closed) {
                ++choice->lateTriggers;
                return;
            }
            auto shown = std::find_if(history.rbegin(), history.rend(),
                                      [&](auto entry) { return entry.first <= when; });
            if (shown != history.rend() && shown->second < choice->begin)
                ++choice->earlyTriggers;
            if (shown != history.rend() && shown->second >= choice->end)
                ++choice->lateTriggers;
            if (shown == history.rend() || shown->second < choice->begin || shown->second >= choice->end)
                return;
            if (effectAt >= 0 && effectTime - effectAt < .15)
                return;
            choice->fired = true;
            choice->hitFrame = shown->second;
            choice->inputTime = when / 1e9;
            choice->inputPoint = p;
            if (!choice->story)
                --choice->ammo;
            foley.cue("shot", 1.f, choice->story && choice->newFeedback ? .78f : 1.f);
            effectAt = effectTime;
            effectPoint = p;
            choice->selected = "miss";
            for (const auto &region : choice->regions) {
                if (!region.covers(shown->second, p))
                    continue;
                choice->selected = region.id;
                break;
            }
            choice->directStoryWeak = choice->story && choice->protectAssist && choice->selected == choice->answer;
            if (choice->selected == "miss" && choice->assist) {
                for (const auto &region : choice->regions) {
                    if (std::find(choice->eligible.begin(), choice->eligible.end(), region.id) ==
                        choice->eligible.end())
                        continue;
                    if (region.covers(shown->second, p, choice->assist) &&
                        !guardBlocksAssist(*choice, region, shown->second, p)) {
                        choice->selected = region.id;
                        break;
                    }
                }
            }
            if (!choice->story &&
                (choice->selected == "miss" || std::find(choice->guards.begin(), choice->guards.end(),
                                                         choice->selected) != choice->guards.end())) {
                ++choice->wasted;
                choice->fired = false;
                foley.cue("miss");
            } else {
                if (choice->newFeedback && choice->story) {
                    const bool protectedHit = std::find(choice->guards.begin(), choice->guards.end(),
                                                        choice->selected) != choice->guards.end();
                    foley.cue(protectedHit ? "civilian" : choice->selected == "miss" ? "miss"
                             : choice->protectAssist && !choice->directStoryWeak ? "hit_ceramic" : "canister");
                } else
                    foley.cue(choice->selected == "miss" ? "miss" : "hit");
                if (!choice->story && choice->selected == choice->answer &&
                    choice->partialHits + choice->specialDamage + 1 < choice->strength) {
                    ++choice->partialHits;
                    choice->fired = false;
                }
            }
        };
        auto reload = [&] {
            if (arrows && (!choice || !choice->story) && !paused && *arrows < 8 && reloadLeft <= 0) {
                const double base = choice ? choice->reloadDuration : travel.duration;
                reloadLeft = (choice && choice->linyuan) ? (.16 + .055 * (8 - *arrows)) * (base / .6) : base;
                foley.cue("reload");
            }
        };
        auto expose = [&] {
            if (!choice || paused || choice->story || choice->fired || choice->spent ||
                displayed < choice->begin || displayed >= choice->end)
                return;
            auto region = std::find_if(choice->regions.begin(), choice->regions.end(),
                                       [&](const auto &r) { return r.id == choice->answer; });
            if (region == choice->regions.end() || displayed < region->begin || displayed >= region->end)
                return;
            if (!choice->canExpose && !choice->canStrike)
                return;
            choice->spent = true;
            foley.cue("special");
            auto outline = region->outline(displayed);
            effectPoint = {};
            for (auto p : outline) {
                effectPoint.x += p.x;
                effectPoint.y += p.y;
            }
            effectPoint.x /= outline.size();
            effectPoint.y /= outline.size();
            effectAt = effectTime;
            if (choice->canStrike) {
                choice->specialDamage = std::min(2, choice->strength - choice->partialHits);
                if (choice->specialDamage + choice->partialHits >= choice->strength) {
                    choice->fired = choice->specialFinish = true;
                    choice->selected = choice->answer;
                }
                return;
            }
            choice->exposed = true;
            exposedLeft = 3.;
            const double speed = std::min(1., (choice->end - displayed) / 72.);
            sound.begin(movie, displayed, speed, now());
        };
        const double tick = now();
        if (!paused)
            effectTime += tick - previous;
        if (!paused && reloadLeft > 0) {
            reloadLeft = std::max(0., reloadLeft - (tick - previous));
            if (reloadLeft == 0 && arrows) {
                *arrows = 8;
                if (choice)
                    ++choice->reloads;
                if (travel.completed)
                    ++*travel.completed;
                foley.cue("ready");
            }
        }
        if (!paused && exposedLeft > 0)
            exposedLeft = std::max(0., exposedLeft - (tick - previous));
        previous = tick;
        if (receiver)
            receiver->poll(SDL_GetTicks(), [&](RemoteAction action, Point raw) {
                if (action == RemoteAction::start) {
                    if (paused) {
                        if (receiver->hasLock())
                            pause(false);
                    } else
                        skip = true;
                }
                if (action == RemoteAction::lost || action == RemoteAction::exit)
                    pause(true);
                if (action == RemoteAction::aim || action == RemoteAction::shoot)
                    aim = {raw.x * 1280 / 1920., raw.y * 720 / 1080.};
                if (action == RemoteAction::shoot)
                    if (aim.x < 0 || aim.x >= 1280 || aim.y < 0 || aim.y >= 720)
                        reload();
                    else
                        fire(aim, SDL_GetTicksNS());
                if (action == RemoteAction::reload)
                    reload();
                if (action == RemoteAction::special)
                    expose();
            });
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            gamepad.poll(
                e, aim,
                [&](Point p, uint64_t when) {
                    if (paused)
                        pause(false);
                    else if (choice)
                        fire(p, when);
                    else if (!travel.boss.active)
                        skip = true;
                },
                reload,
                [&] {
                    if (choice && (choice->canExpose || choice->canStrike))
                        expose();
                },
                [&] {
                    if (choice || travel.boss.active)
                        pause(!paused);
                    else
                        skip = true;
                });
            if (e.type == SDL_EVENT_QUIT)
                return FilmEnd::quit;
            if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && !automated)
                pause(true);
            if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {
                if (e.key.key == SDLK_ESCAPE || (paused && e.key.key == SDLK_RETURN))
                    pause(!paused);
                else if (choice && e.key.key == SDLK_SPACE)
                    expose();
                else if (!travel.boss.active && (e.key.key == SDLK_SPACE || e.key.key == SDLK_RETURN))
                    skip = true;
                else if (e.key.key == SDLK_F11)
                    SDL_SetWindowFullscreen(window, !(SDL_GetWindowFlags(window) & SDL_WINDOW_FULLSCREEN));
                else if (e.key.key == SDLK_R)
                    reload();
            }
            if (e.type == SDL_EVENT_MOUSE_MOTION) {
                SDL_ConvertEventToRenderCoordinates(renderer, &e);
                aim = {e.motion.x, e.motion.y};
            }
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button == SDL_BUTTON_LEFT) {
                SDL_ConvertEventToRenderCoordinates(renderer, &e);
                if (paused)
                    pause(false);
                else if (choice)
                    fire({e.button.x, e.button.y}, e.button.timestamp);
                else if (!travel.boss.active && e.button.x > 1050 && e.button.y > 635)
                    skip = true;
            }
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button == SDL_BUTTON_RIGHT)
                reload();
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button == SDL_BUTTON_MIDDLE) {
                if (choice && choice->canExpose)
                    expose();
                else if (choice && choice->canStrike && !paused && !choice->fired &&
                         displayed >= choice->begin && displayed < choice->end)
                    expose();
            }
        }
        gamepad.updateAim(aim, 1280, 720, [&](Point p, uint64_t when) {
            if (choice && !paused)
                fire(p, when);
        });
        if (choice && choice->fired && !paused && effectTime - effectAt >= .34)
            return FilmEnd::selected;
        if (choice && !choice->fired && !paused &&
            (displayed >= choice->end || (choice->exposed && exposedLeft <= 0))) {
            choice->closed = now();
            return FilmEnd::expired;
        }
        if (skip && !choice && !paused)
            return FilmEnd::skipped;
        int frame = sound.localFrame(now());
        if (choice && !slowedWindow && choice->playbackRate != 1. && frame >= choice->begin) {
            frame = choice->begin;
            sound.begin(movie, frame, choice->playbackRate, now());
            slowedWindow = true;
        }
        if (score)
            score->update(!paused);
        if (choice && !choice->fired && frame >= filmEnd && !paused && displayed == filmEnd - 1 &&
            choice->end == filmEnd) {
            const auto cutoff = SDL_GetTicksNS();
            choice->closed = cutoff / 1e9;
            if (automated && choice->boundaryProbes && !sentLate)
                fire({15., 18.}, cutoff);
            return FilmEnd::expired;
        }
        if (frame >= filmEnd && !paused && displayed == filmEnd - 1 &&
            (!dialogue || SDL_GetAudioStreamQueued(dialogue.get()) == 0))
            return FilmEnd::finished;
        const int shown = std::clamp(frame, filmStart, filmEnd - 1);
        if (shown != displayed) {
            const auto *pic = movie.at(shown);
            if (!SDL_UpdateYUVTexture(texture.get(), nullptr, pic->data[0], pic->linesize[0], pic->data[1],
                                      pic->linesize[1], pic->data[2], pic->linesize[2]))
                throw std::runtime_error(SDL_GetError());
            displayed = shown;
            if (!film.cues.empty()) {
                const auto cue = std::find_if(film.cues.begin(), film.cues.end(), [&](const DialogueCue &c) {
                    return shown >= c.begin && shown < c.end;
                });
                const auto *current = cue == film.cues.end() ? nullptr : &*cue;
                if (speaking != current) {
                    dialogue.reset();
                    speaking = current;
                    if (current)
                        say(current->voice);
                }
            }
        }
        SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
        SDL_RenderClear(renderer);
        const double age = effectTime - effectAt;
        const bool civilian =
            choice && choice->newFeedback && choice->fired &&
            std::find(choice->guards.begin(), choice->guards.end(), choice->selected) != choice->guards.end();
        const bool hitAnswer = choice && choice->newFeedback && choice->fired && choice->selected == choice->answer;
        SDL_FRect picture{0, 0, 1280, 720};
        const bool precise = choice && choice->newFeedback && (choice->directStoryWeak || hitAnswer);
        const double shakeSeconds = civilian ? .19 : .14;
        if ((civilian || precise) && choice->shakeEnabled && age < shakeSeconds) {
            const float strength = float(6 * std::max(0., 1. - age / shakeSeconds));
            picture = {float(strength * (std::sin(age * 142.) - 1)),
                       float(strength * (std::cos(age * 116.) - 1)), 1280 + 2 * strength, 720 + 2 * strength};
        }
        SDL_RenderTexture(renderer, texture.get(), nullptr, &picture);
        if (receiver)
            drawGunBorder(ink);
        if (choice && effectAt >= 0 && age < .34 && choice->newFeedback) {
            const Point screenPoint{picture.x + effectPoint.x * picture.w / 1280.,
                                    picture.y + effectPoint.y * picture.h / 720.};
            const Cue fxCue = civilian                     ? Cue::civilian
                              : choice->specialFinish      ? Cue::special
                              : choice->selected == "miss" ? Cue::miss
                                                           : Cue::purify;
            drawLinyuanEffect(ink, fxCue, screenPoint, age, choice->reducedFlash,
                              choice->specialFinish ? 4 : choice->tier, precise || choice->specialFinish,
                              LinyuanImpact::claw, hitAnswer ? choice->hitPoints : 0, choice->material,
                              choice->lives, 0, choice->directStoryWeak, .145);
        } else if (choice && effectAt >= 0 && age < .29) {
            const auto a = Uint8(230 * (1. - age / .29));
            ink.ring(effectPoint, int(8 + 74 * age), {255, 213, 125, a});
            for (int i = 0; i < 10; ++i) {
                const double angle = i * .62831853;
                const float x = float(effectPoint.x + (11 + 120 * age) * std::cos(angle));
                const float y = float(effectPoint.y + (11 + 120 * age) * std::sin(angle));
                ink.box(x, y, 3, 3, {255, 235, 167, a});
            }
        }
        const std::string &caption = speaking ? speaking->subtitle : film.subtitle;
        if (subtitles && !caption.empty() && (speaking || displayed >= 5) &&
            (!choice || displayed < choice->begin)) {
            ink.box(100, 622, 1080, 52, {9, 12, 20, 185});
            ink.text(640, 632, 25, caption, ivory, true);
        }
        if (choice && displayed >= choice->begin && displayed < choice->end) {
            if (windowOpenAt < 0)
                windowOpenAt = effectTime;
            ink.box(250, 610, 780, 54, {9, 12, 20, 206});
            ink.box(250, 610, 780, 2, {204, 158, 86, 175});
            ink.text(640, 624, 24, choice->prompt, gold, true);
            if (choice->strength > 1)
                ink.text(640, 577, 20,
                         "符印  " + std::to_string(choice->partialHits + choice->specialDamage) + " / " +
                             std::to_string(choice->strength),
                         ivory, true);
            if (aim.x >= 0 && choice->newFeedback) {
                bool protectedPoint = false, targetPoint = false;
                for (const auto &region : choice->regions)
                    if (region.covers(displayed, aim)) {
                        protectedPoint = std::find(choice->guards.begin(), choice->guards.end(), region.id) !=
                                         choice->guards.end();
                        targetPoint = region.id == choice->answer;
                        break;
                    }
                drawLinyuanReticle(ink, aim, choice->ammo, reloadLeft > 0, targetPoint, targetPoint,
                                   protectedPoint, choice->canStrike);
            } else if (aim.x >= 0)
                ink.ring(aim, 9, ivory);
            if (choice->regions.size() == 1 || choice->highlight || choice->exposed || choice->protectAssist) {
                const auto mark =
                    std::find_if(choice->regions.begin(), choice->regions.end(),
                                 [&](const TrackedRegion &z) { return z.id == choice->answer; });
                if (mark != choice->regions.end() && displayed >= mark->begin && displayed < mark->end) {
                    const auto poly = mark->outline(displayed);
                    Point center{};
                    for (const auto &p : poly) {
                        center.x += p.x;
                        center.y += p.y;
                    }
                    center.x /= poly.size();
                    center.y /= poly.size();
                    if (choice->linyuan && choice->newFeedback) {
                        const double span = std::max(1, choice->end - choice->begin);
                        const double progress = std::clamp((displayed - choice->begin) / span, 0., 1.);
                        const double urgency = progress >= .65 ? (progress - .65) / .35 : 0.;
                        drawLinyuanTargetLock(ink, center, 34.f, effectTime,
                                              std::max(0., effectTime - windowOpenAt), urgency,
                                              choice->answer == "fireball");
                    } else
                        ink.ring(center, 30, gold);
                }
            }
        } else if (!choice && !travel.boss.active) {
            ink.box(1080, 674, 187, 36, {9, 12, 20, 175});
            ink.text(1173, 680, 17, paused ? "点击继续" : "空格  跳过本段", ivory, true);
        }
        if (choice && !choice->story && choice->linyuan) {
            const int done = choice->bossStepDone + (choice->fired && choice->selected == choice->answer ? 1 : 0);
            drawBossTrialHud(ink, choice->lives, choice->ammo, reloadLeft, choice->bossPhase, done,
                             choice->bossStepTotal, choice->canStrike);
            if (automated && choice->ammo < choice->strength - choice->partialHits - choice->specialDamage)
                reload();
        } else if (!choice && travel.boss.active) {
            drawBossTrialHud(ink, travel.boss.lives, arrows ? *arrows : travel.boss.ammo, reloadLeft,
                             travel.boss.phase, travel.boss.done, travel.boss.total, travel.boss.canStrike);
        } else if (choice && !choice->story) {
            ink.box(26, 24, 396, 52, {9, 12, 20, 185});
            ink.text(44, 38, 20,
                     "生命 " + std::to_string(choice->lives) + "     " +
                         (reloadLeft > 0 ? "更换符匣" : "符箭 " + std::to_string(choice->ammo) + " / 8") +
                         (choice->canStrike ? "   空格 雷符" : ""),
                     ivory);
            if (automated && choice->ammo < choice->strength - choice->partialHits - choice->specialDamage)
                reload();
        }
        if (paused) {
            ink.box(0, 0, 1280, 720, {8, 12, 19, 164});
            ink.text(640, 315, 38, "剧情暂停", ivory, true);
            ink.text(640, 378, 20, "按 Esc 或点击画面继续", gold, true);
        }
        CampaignRecording::frame(renderer);
        if (!SDL_RenderPresent(renderer))
            throw std::runtime_error(SDL_GetError());
        submitted = SDL_GetTicksNS();
        if (choice && !paused && displayed >= choice->begin && displayed < choice->end && choice->firstOpen < 0)
            choice->firstOpen = submitted / 1e9;
        if (choice && choice->inputTime >= 0 && choice->firstFeedback < 0)
            choice->firstFeedback = submitted / 1e9;
        if (automated && film.autoSkip && !choice && !skipSent && displayed >= 8) {
            SDL_Event key{};
            key.type = SDL_EVENT_KEY_DOWN;
            key.key.key = SDLK_SPACE;
            key.key.timestamp = submitted;
            if (!SDL_PushEvent(&key))
                throw std::runtime_error(SDL_GetError());
            skipSent = true;
        }
        history.emplace_back(submitted, displayed);
        while (submitted - history.front().first > 300000000)
            history.pop_front();
        if (choice && automated && choice->boundaryProbes) {
            if (!sentEarly && displayed == choice->begin - 1) {
                sentEarly = true;
                fire({15., 18.}, submitted);
            }
            if (!sentLate && displayed >= choice->end) {
                sentLate = true;
                fire({15., 18.}, submitted);
            }
        }
        if (choice && automated && choice->pauseProbe && displayed >= choice->begin) {
            if (!probePaused) {
                pause(true);
                probePaused = true;
            } else if (!probeResumed && now() - pauseStart >= .4) {
                pause(false);
                probeResumed = true;
            }
        }
        if (choice && automated && !choice->replayAnswer.empty() && !choice->fired &&
            displayed >= choice->begin + choice->replayOffset && displayed < choice->end) {
            if (choice->recordedPoint) {
                fire(*choice->recordedPoint, submitted);
                continue;
            }
            if (choice->autoSpecial && !choice->spent && (choice->canExpose || choice->canStrike)) {
                expose();
                if (choice->spent)
                    continue;
            }
            if (choice->replayAnswer == "miss") {
                fire({15., 18.}, submitted);
                continue;
            }
            auto wanted =
                std::find_if(choice->regions.begin(), choice->regions.end(),
                             [&](const TrackedRegion &r) { return r.id == choice->replayAnswer; });
            if (wanted == choice->regions.end())
                throw std::runtime_error("Unknown replay target");
            if (displayed < wanted->begin || displayed >= wanted->end)
                continue;
            auto poly = wanted->outline(displayed);
            Point center{};
            for (auto p : poly) {
                center.x += p.x;
                center.y += p.y;
            }
            fire({center.x / poly.size(), center.y / poly.size()}, submitted);
        }
        SDL_Delay(3);
    }
}

void ChapterScore::add(const ChapterScore &s) {
    points += s.points;
    hits += s.hits;
    shots += s.shots;
    combo = std::max(combo, s.combo);
    damage += s.damage;
    purified += s.purified;
}

std::string ChapterScore::grade() const {
    const double accuracy = shots ? double(hits) / shots : 0.;
    if (accuracy >= .90 && damage == 0 && purified > 0)
        return "S";
    if (accuracy >= .75 && damage <= 2)
        return "A";
    if (accuracy >= .50)
        return "B";
    return "C";
}

Progress Progress::load(const fs::path &file) {
    Progress state;
    if (!fs::exists(file))
        return state;
    const auto data = Json::parse(std::ifstream(file));
    if (data.at("version") != 1)
        throw std::runtime_error("Unsupported campaign save version");
    state.next = data.at("next");
    state.difficulty = data.at("difficulty");
    state.lives = data.at("lives");
    state.energy = data.at("energy");
    state.arrows = std::clamp(data.value("arrows", 8), 0, 8);
    state.reloadRemaining = std::clamp(data.value("reload_remaining", 0.), 0., .8);
    state.subtitles = data.at("subtitles");
    state.lastStoryCivilian = data.value("last_story_civilian", false);
    state.musicVolume = std::clamp(data.value("music", 60), 0, 100);
    state.effectsVolume = std::clamp(data.value("effects", 80), 0, 100);
    state.voiceVolume = std::clamp(data.value("voice", 100), 0, 100);
    for (const auto &[id, v] : data.at("scores").items()) {
        ChapterScore s{v.at("points"), v.at("hits"),   v.at("shots"),
                       v.at("combo"),  v.at("damage"), v.at("purified")};
        if (s.points < 0 || s.hits < 0 || s.shots < s.hits || s.combo < 0 || s.damage < 0 || s.purified < 0)
            throw std::runtime_error("Invalid campaign score");
        state.scores.emplace(id, s);
    }
    return state;
}

void Progress::save(const fs::path &file) const {
    if (file.empty())
        return;
    fs::create_directories(file.parent_path());
    Json values = Json::object();
    for (const auto &[id, s] : scores)
        values[id] = {{"points", s.points}, {"hits", s.hits},     {"shots", s.shots},
                      {"combo", s.combo},   {"damage", s.damage}, {"purified", s.purified}};
    Json data{{"version", 1},
              {"next", next},
              {"difficulty", difficulty},
              {"lives", lives},
              {"energy", energy},
              {"arrows", arrows},
              {"reload_remaining", reloadRemaining},
              {"subtitles", subtitles},
              {"last_story_civilian", lastStoryCivilian},
              {"music", musicVolume},
              {"effects", effectsVolume},
              {"voice", voiceVolume},
              {"scores", values}};
    const auto tmp = fs::path(file.wstring() + L"." + std::to_wstring(GetCurrentProcessId()) + L".tmp");
    {
        std::ofstream stream(tmp, std::ios::binary | std::ios::trunc);
        stream.exceptions(std::ios::failbit | std::ios::badbit);
        stream << data.dump(2) << '\n';
        stream.close();
    }
    if (!MoveFileExW(tmp.c_str(), file.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        fs::remove(tmp);
        throw std::runtime_error("Cannot replace the campaign checkpoint");
    }
}
Campaign::Campaign(const CampaignWorld &world, const std::string &name) : linyuan(world.linyuan()) {
    auto checkId = [](const std::string &id) {
        if (id.empty() ||
            id.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_") != std::string::npos)
            throw std::runtime_error("Invalid campaign identifier: " + id);
    };
    checkId(name);
    const auto data = readCampaignJson(world.data() / (name + ".json"));
    const auto media = readCampaignJson(world.data() / "drama.json");
    title = data.at("title");
    titleArt = world.assets() / "title.bmp";
    std::set<std::string> chapters, ids;
    for (const auto &chapter : data.at("chapters")) {
        const std::string id = chapter.at("id");
        checkId(id);
        if (!chapters.insert(id).second || chapter.at("stages").empty())
            throw std::runtime_error("Invalid campaign chapter: " + id);
        for (const auto &item : chapter.at("stages")) {
            Stage stage;
            stage.id = item.at("id");
            stage.heading = chapter.at("heading");
            stage.chapter = id;
            stage.linyuan = world.linyuan();
            stage.allowSpecial = item.value("allow_special", !world.linyuan());
            stage.music = item.value("music", "");
            if (!stage.music.empty())
                checkId(stage.music);
            checkId(stage.id);
            if (!ids.insert(stage.id).second)
                throw std::runtime_error("Duplicate stage: " + stage.id);
            if (item.at("type") == "encounter") {
                stage.level = item.at("level");
                checkId(stage.level);
                if (!fs::is_regular_file(world.data() / stage.level / "level.json"))
                    throw std::runtime_error("Missing playable stage: " + stage.level);
            } else if (item.at("type") == "film") {
                for (const auto &shot : item.at("takes")) {
                    const std::string take = shot.at("id");
                    checkId(take);
                    const int count = media.at(take).at("frames");
                    if (count <= 0 || !fs::is_regular_file(world.assets() / "drama" / (take + ".mp4")))
                        throw std::runtime_error("Missing story take: " + take);
                    const auto voice = shot.value("voice", "");
                    if (!voice.empty()) {
                        auto sep = voice.find('/');
                        if (sep == std::string::npos || voice.find('/', sep + 1) != std::string::npos)
                            throw std::runtime_error("Invalid voice asset identifier");
                        checkId(voice.substr(0, sep));
                        checkId(voice.substr(sep + 1));
                    }
                    stage.films.push_back({take, shot.value("subtitle", ""), count, voice});
                    stage.films.back().cues = readDialogue(shot, count);
                    stage.films.back().wallClockLimited = world.linyuan();
                    if (shot.contains("after_civilian"))
                        stage.films.back().afterCivilian = shot.at("after_civilian").get<bool>();
                }
                if (stage.films.empty())
                    throw std::runtime_error("Empty cinematic: " + stage.id);
            } else if (item.at("type") == "card") {
                stage.cardMillis = item.value("milliseconds", 1000);
                stage.cardText = item.at("text");
                if (stage.cardMillis <= 0 || stage.cardText.empty())
                    throw std::runtime_error("Invalid title card: " + stage.id);
            } else if (item.at("type") == "trial") {
                stage.trial = item.at("trial");
            } else {
                throw std::runtime_error("Unrecognized stage: " + stage.id);
            }
            stages.push_back(std::move(stage));
        }
    }
    if (stages.empty())
        throw std::runtime_error("The campaign has no stages");
}

size_t Campaign::locate(const std::string &id) const {
    if (id.empty())
        return 0;
    if (id == "@complete")
        return stages.size();
    const auto it = std::find_if(stages.begin(), stages.end(), [&](const Stage &s) { return s.id == id; });
    if (it == stages.end())
        throw std::runtime_error("Unrecognized campaign checkpoint: " + id);
    return size_t(it - stages.begin());
}

FilmEnd playTrial(SDL_Window *window, SDL_Renderer *renderer, const CampaignWorld &world, const Stage &stage,
                  Progress &state, Receiver *gun, bool automated, const fs::path &evidence,
                  const std::string &scenario, ScoreAudio *score, int &completedReloads, bool newFeedback,
                  bool reducedFlash, const fs::path &inputSource, bool shakeEnabled) {
    const auto recorded = inputSource.empty() ? Json::array() : readCampaignJson(inputSource);
    const auto index = readCampaignJson(world.data() / "drama.json");
    auto film = [&](const std::string &id) {
        Film result{id, "", index.at(id).at("frames")};
        result.wallClockLimited = world.linyuan();
        return result;
    };
    const auto media = world.assets() / "drama";
    const auto &trial = stage.trial;
    std::string step = trial.at("first");
    ChapterScore section;
    int lives = state.lives, energy = state.energy, ammo = state.arrows, combo = 0;
    int visits = 0;
    bool safeRescue = true;
    int retries = 0;
    int bossHp = -1;
    std::string bossStep;
    Json trace = Json::array();
    while (step != "@complete") {
        if (automated && ++visits > 150)
            throw std::runtime_error("Trial replay did not converge: " + stage.id);
        const auto &record = trial.at("steps").at(step);
        const std::string take = record.at("take");
        Film movie = film(take);
        movie.startFrame = record.value("start_frame", 0);
        movie.endFrame = record.value("end_frame", movie.frames);
        movie.voice = record.value("voice", "");
        movie.subtitle = record.value("subtitle", "");
        movie.cues = readDialogue(record, movie.frames);
        const auto annotation = readCampaignJson(world.data() / "regions" / (take + ".json"));
        if (annotation.at("sha256") != index.at(take).at("sha256"))
            throw std::runtime_error("Outdated story region: " + take);
        const auto &windowFrames = record.at("window");
        int start = windowFrames.at(0);
        int length = windowFrames.at(1);
        const bool storyShot = record.value("story_shot", false);
        double windowRate = record.value("window_rate", 1.);
        if (!(windowRate > 0 && windowRate <= 1.))
            throw std::runtime_error("Invalid trial playback rate: " + step);
        if (storyShot && record.contains("window_seconds")) {
            const double mult = world.linyuan()
                                    ? (state.difficulty == "easy" ? 1.5 : state.difficulty == "hard" ? .6 : 1.)
                                    : 1.;
            const double desired = record.at("window_seconds").get<double>() * mult;
            windowRate = double(length) / (desired * 24.);
        } else if (storyShot) {
            length = state.difficulty == "easy" ? 72 : state.difficulty == "hard" ? 29 : 48;
        } else {
            const bool flight = record.value("projectile", false);
            const double scale = state.difficulty == "easy"   ? (flight ? 1.3 : 1.4)
                                 : state.difficulty == "hard" ? (flight ? .7 : .65)
                                                              : 1.;
            length = std::min(movie.endFrame - start - 1, int(std::lround(length * scale)));
        }
        FilmChoice target{start, start + length, record.at("prompt"), record.at("answer")};
        target.playbackRate = windowRate;
        target.linyuan = world.linyuan();
        target.newFeedback = newFeedback;
        target.reducedFlash = reducedFlash;
        target.shakeEnabled = shakeEnabled;
        target.protectAssist = world.linyuan();
        target.material = record.value("material", storyShot ? "feather" : "ceramic");
        target.tier = record.value("tier", 2);
        target.replayAnswer = target.answer;
        target.assist = state.difficulty == "easy" ? 24 : state.difficulty == "hard" ? 0 : 12;
        target.story = storyShot;
        const int baseBossHp = record.value("boss_hp", 0);
        const int adj = state.difficulty == "easy" ? -1 : state.difficulty == "hard" ? 1 : 0;
        if (baseBossHp > 0) {
            if (bossStep != step) {
                bossStep = step;
                bossHp = std::max(1, baseBossHp + adj);
            }
            target.strength = 1;
        } else {
            target.strength = record.value("strength", 1);
        }
        target.hitPoints = record.at("outcomes").at(target.answer).value("points", 0);
        if (world.linyuan() && stage.id == "taotie") {
            if (step.starts_with("p1_")) {
                target.bossPhase = 1;
                target.bossStepTotal = 6;
                target.bossStepDone = std::clamp(std::stoi(step.substr(3)) - 1, 0, 6);
            } else if (step.starts_with("p2_")) {
                target.bossPhase = 2;
                target.bossStepTotal = 3;
                target.bossStepDone = std::clamp(std::stoi(step.substr(3)) - 1, 0, 3);
            } else {
                const int total = std::max(1, baseBossHp + adj);
                target.bossPhase = 3;
                target.bossStepTotal = total;
                target.bossStepDone = std::clamp(total - bossHp, 0, total);
            }
        }
        if (target.strength < 1 || target.strength > 6 || (storyShot && target.strength != 1))
            throw std::runtime_error("Invalid target strength: " + step);
        target.ammo = ammo;
        target.lives = lives;
        target.highlight = record.value("highlight", false);
        target.guards = record.value("guards", std::vector<std::string>{});
        const int capacity = state.difficulty == "easy" ? 15 : state.difficulty == "hard" ? 25 : 20;
        target.canExpose = record.value("expose", false) && energy == capacity;
        target.canStrike = record.value("thunder_strike", false) && !target.canExpose && energy == capacity;
        if (baseBossHp > 0) {
            if (scenario == "boss-thunder" || scenario == "boss-thunder-3")
                target.autoSpecial = target.canStrike;
            else if (scenario == "boss-thunder-2")
                target.autoSpecial = target.canStrike && bossHp <= 2;
            else if (scenario == "boss-thunder-1")
                target.autoSpecial = target.canStrike && bossHp <= 1;
        } else {
            target.autoSpecial = scenario == "boss-thunder";
        }
        target.reloadDuration = state.difficulty == "easy" ? .4 : state.difficulty == "hard" ? .8 : .6;
        if (start < movie.startFrame || length <= 0 || target.end > movie.endFrame)
            throw std::runtime_error("Invalid story window: " + step);
        for (const auto &key : record.at("zones")) {
            TrackedRegion region{key};
            if (world.linyuan() && record.at("outcomes").at(region.id).value("civilian", false))
                target.guards.push_back(region.id);
            if (record.at("outcomes").at(region.id).value("points", 0) > 0)
                target.eligible.push_back(region.id);
            if (record.contains("zone_windows") && record.at("zone_windows").contains(region.id)) {
                const auto &bounds = record.at("zone_windows").at(region.id);
                region.begin = bounds.at(0);
                region.end = bounds.at(1);
            }
            for (const auto &pose : annotation.at("regions").at(region.id)) {
                std::vector<Point> poly;
                for (const auto &pair : pose.at("polygon"))
                    poly.push_back({pair.at(0), pair.at(1)});
                if (poly.size() < 3 ||
                    (!region.outlines.empty() && poly.size() != region.outlines.begin()->second.size()))
                    throw std::runtime_error("Invalid story outline: " + take);
                region.outlines.emplace(pose.at("frame").get<int>(), std::move(poly));
            }
            if (region.outlines.empty() || region.outlines.begin()->first > start ||
                region.outlines.rbegin()->first < target.end - 1)
                throw std::runtime_error("Incomplete tracking: " + take);
            target.regions.push_back(std::move(region));
        }
        if (target.protectAssist)
            std::stable_partition(target.regions.begin(), target.regions.end(),
                                  [&](const TrackedRegion &region) {
                                      return std::find(target.guards.begin(), target.guards.end(), region.id) !=
                                             target.guards.end();
                                  });
        if (storyShot && scenario == "story-miss")
            target.replayAnswer = "miss";
        if (storyShot &&
            (scenario == "story-timeout" || scenario == "story-boundaries" || scenario == "story-pause"))
            target.replayAnswer.clear();
        if (world.linyuan() && storyShot) {
            target.boundaryProbes = scenario == "story-boundaries";
            target.pauseProbe = scenario == "story-pause";
            if (scenario == "story-first")
                target.replayOffset = 0;
            if (scenario == "story-last")
                target.replayOffset = length - 1;
        }
        if (world.linyuan() && storyShot &&
            (scenario == "story-civilian" || scenario == "retry" || scenario == "give-up"))
            for (const auto &zone : record.at("zones")) {
                const std::string region = zone;
                if (record.at("outcomes").at(region).value("civilian", false))
                    target.replayAnswer = region;
            }
        if (scenario == "fireball-miss" &&
            ((step == "fireball_1" && trace.empty()) ||
             (step == "p2_1" && std::none_of(trace.begin(), trace.end(),
                                             [](const Json &e) { return e.at("step") == "p2_1"; }))))
            target.replayAnswer.clear();
        if (stage.id == "hall_of_mirrors" && step == "three" && scenario == "mirror-right")
            target.replayAnswer = "right";
        if (stage.id == "nine_lanterns" && step == "signal_1" && trace.empty() &&
            scenario == "dragon-order")
            target.replayAnswer = "head_3";
        if (stage.id == "west_possessions" && scenario == "civilian-retry" && retries == 0)
            target.replayAnswer = "civilian";
        if (!inputSource.empty()) {
            const auto &previous = recorded.at(trace.size());
            if (previous.at("step") != step || previous.at("take") != take)
                throw std::runtime_error("Recorded trial step mismatch: " + step);
            const int hit = previous.at("hit_frame");
            target.replayAnswer = hit < 0 ? "" : previous.at("input").get<std::string>();
            if (hit >= 0) {
                target.replayOffset = hit - start;
                target.recordedPoint = Point{previous.at("input_x"), previous.at("input_y")};
            }
        }
        auto result = playFilm(
            window, renderer, media, movie, state.subtitles, gun, automated, &target, score,
            state.voiceVolume / 100.f, state.effectsVolume / 100.f,
            {&ammo, &state.reloadRemaining, target.reloadDuration, &completedReloads, &state.pausedSeconds});
        if (result == FilmEnd::quit)
            return result;
        const auto key = target.fired ? target.selected : std::string("timeout");
        if (!inputSource.empty() && (recorded.at(trace.size()).at("input") != key ||
                                     recorded.at(trace.size()).at("hit_frame") != target.hitFrame))
            throw std::runtime_error("Recorded story sword produced a different result: " + step);
        const auto &branch = record.at("outcomes").at(key);
        const bool civilian = branch.value("civilian", false);
        if (storyShot)
            state.lastStoryCivilian = civilian;
        bool multiPhaseFlinch = false;
        std::string nextStep = branch.at("next");
        std::string responseTake = branch.value("response", "");
        if (key == target.answer && record.contains("intercept_windows")) {
            for (const auto &iw : record.at("intercept_windows")) {
                if (iw.at(0).get<int>() <= target.hitFrame && target.hitFrame < iw.at(1).get<int>()) {
                    responseTake = iw.at(2).get<std::string>();
                    break;
                }
            }
        }
        if (baseBossHp > 0 && target.fired && key == target.answer) {
            bossHp -= target.specialFinish ? 2 : 1;
            if (bossHp > 0) {
                multiPhaseFlinch = true;
                nextStep = step;
                responseTake = record.value("flinch_response", responseTake);
            } else {
                bossStep.clear();
                responseTake = record.value("kill_response", responseTake);
            }
        }
        const int baseAward = multiPhaseFlinch ? 25 : branch.value("points", 0);
        int award = civilian ? -100 : baseAward;
        if (!storyShot && !multiPhaseFlinch && award > 0 && branch.value("purified", 0) > 0 && !target.specialFinish) {
            const double reaction =
                1. + .5 * std::clamp(1. - double(target.hitFrame - start) / std::max(1, length), 0., 1.);
            if (baseAward == 500)
                award += 200;
            award = int(
                std::lround(award * reaction * std::min(3., 1. + .05 * (combo + target.partialHits + 1))));
        }
        if (civilian)
            safeRescue = false;
        if (target.spent)
            energy = 0;
        const int harm = civilian && state.difficulty == "easy" ? 0 : branch.value("damage", 0);
        if (score && !(newFeedback && storyShot && civilian)) {
            if (civilian)
                score->cue("civilian");
            else if (harm)
                score->cue("hurt");
            else if (target.specialFinish)
                score->cue("special");
            else if (award > 0 && record.value("projectile", false))
                score->cue("intercept");
            else if (multiPhaseFlinch)
                score->cue("hit_ceramic");
            else if (branch.value("purified", 0) > 0)
                score->cue("purify");
            else if (world.linyuan() && newFeedback && storyShot && key == target.answer)
                score->cue("kill", 1.f, .64f);
        }
        ammo = target.ammo;
        if (!world.linyuan() || !storyShot)
            section.shots += (target.fired && !target.specialFinish) + target.wasted + target.partialHits;
        section.hits += target.partialHits;
        section.points += 25 * target.partialHits;
        if (target.partialHits) {
            if (!target.spent)
                energy = std::min(capacity, energy + target.partialHits);
            combo += target.partialHits;
            section.combo = std::max(section.combo, combo);
        }
        if (target.wasted) {
            combo = 0;
            energy = std::max(0, energy - 2 * target.wasted);
        }
        if (!world.linyuan() || !storyShot)
            section.hits += target.fired && award > 0 && !target.specialFinish;
        section.points += award;
        if (!world.linyuan())
            section.points = std::max(-state.scores[stage.chapter].points, section.points);
        if (!multiPhaseFlinch)
            section.purified += branch.value("purified", 0);
        if (harm || civilian) {
            lives -= harm;
            section.damage += harm;
            combo = energy = 0;
        } else if (!storyShot && target.fired && award > 0 && !target.specialFinish) {
            section.combo = std::max(section.combo, ++combo);
            energy = std::min(state.difficulty == "easy"   ? 15
                              : state.difficulty == "hard" ? 25
                                                           : 20,
                              energy + 1);
        } else if (!storyShot && target.fired) {
            energy = std::max(0, energy - 2);
            combo = 0;
        }
        trace.push_back({{"step", step},
                         {"take", take},
                         {"input", key},
                         {"points", award},
                         {"lives", lives},
                         {"arrows", ammo},
                         {"partial_hits", target.partialHits},
                         {"reloads", target.reloads},
                         {"warning_frame", start},
                         {"window_end", target.end},
                         {"hit_frame", target.hitFrame},
                         {"direct_weak", target.directStoryWeak},
                         {"t_open", target.firstOpen},
                         {"t_closed", target.closed},
                         {"t_input", target.inputTime},
                         {"t_feedback", target.firstFeedback},
                         {"input_x", target.inputPoint.x},
                         {"input_y", target.inputPoint.y},
                         {"prewindow_inputs", target.earlyTriggers},
                         {"postwindow_inputs", target.lateTriggers},
                         {"damage", harm},
                         {"special", target.spent},
                         {"boss_hp", bossHp},
                         {"attempt", retries + 1},
                         {"response", responseTake}});
        if (lives <= 0) {
            if (!automated) {
                SDL_MessageBoxButtonData options[] = {
                    {SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT, 1, "重试此段"},
                    {SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT, 0, "结束游戏"}};
                SDL_MessageBoxData box{SDL_MESSAGEBOX_INFORMATION,
                                       window,
                                       world.linyuan() ? "剑穗已尽" : "灯火未平",
                                       world.linyuan() ? "剑穗熄灭。要重新尝试这一段吗？"
                                                       : "灯火熄灭。要重新尝试这一段吗？",
                                       2,
                                       options,
                                       nullptr};
                int pressed = -1;
                if (!SDL_ShowMessageBox(&box, &pressed) || pressed != 1)
                    return FilmEnd::quit;
            }
            section = {};
            safeRescue = true;
            state.reloadRemaining = 0;
            bossStep.clear();
            bossHp = -1;
            ++retries;
            lives = state.difficulty == "easy" ? 5 : 3;
            energy = combo = 0;
            ammo = 8;
            step = trial.at("first");
            continue;
        }
        const BossOverlay bossHud{
            world.linyuan() && stage.id == "taotie",
            lives,
            ammo,
            target.bossPhase,
            target.bossStepDone + (target.fired && key == target.answer ? 1 : 0),
            target.bossStepTotal,
            false,
        };
        if (!responseTake.empty()) {
            auto response = film(responseTake);
            response.voice = branch.value("response_voice", "");
            response.subtitle = branch.value("response_subtitle", "");
            if (playFilm(window, renderer, media, response, state.subtitles, gun, automated, nullptr, score,
                         state.voiceVolume / 100.f, state.effectsVolume / 100.f,
                         {&ammo, &state.reloadRemaining, target.reloadDuration, &completedReloads,
                          &state.pausedSeconds, bossHud}) == FilmEnd::quit)
                return FilmEnd::quit;
        }
        if (!multiPhaseFlinch && branch.contains("transition")) {
            auto trans = film(branch.at("transition"));
            trans.voice = branch.value("transition_voice", "");
            trans.subtitle = branch.value("transition_subtitle", "");
            if (playFilm(window, renderer, media, trans, state.subtitles, gun, automated, nullptr, score,
                         state.voiceVolume / 100.f, state.effectsVolume / 100.f,
                         {&ammo, &state.reloadRemaining, target.reloadDuration, &completedReloads,
                          &state.pausedSeconds, bossHud}) == FilmEnd::quit)
                return FilmEnd::quit;
        }
        step = nextStep;
    }
    if (safeRescue)
        section.points += trial.value("rescue_bonus", 0);
    state.scores[stage.chapter].add(section);
    state.lives = lives;
    state.energy = energy;
    state.arrows = ammo;
    if (!evidence.empty()) {
        fs::create_directories(evidence);
        std::ofstream(evidence / (stage.id + ".json")) << trace.dump(2) << '\n';
    }
    return FilmEnd::finished;
}

bool chapterResults(SDL_Renderer *renderer, const Stage &stage, const ChapterScore &score,
                    Receiver *receiver, bool automated, ScoreAudio *music, bool linyuan,
                    const fs::path &titleArt) {
    Ink ink(renderer);
    const auto accuracy = score.shots ? std::lround(100. * score.hits / score.shots) : 0;
    const auto entered = SDL_GetTicks();
    Texture backdrop(nullptr, SDL_DestroyTexture);
    if (linyuan && !titleArt.empty() && fs::is_regular_file(titleArt)) {
        const auto name = titleArt.u8string();
        std::unique_ptr<SDL_Surface, decltype(&SDL_DestroySurface)> art(
            SDL_LoadBMP(reinterpret_cast<const char *>(name.c_str())), SDL_DestroySurface);
        if (art)
            backdrop.reset(SDL_CreateTextureFromSurface(renderer, art.get()));
    }
    for (;;) {
        if (music)
            music->update(true);
        SDL_SetRenderDrawColor(renderer, 14, 21, 28, 255);
        SDL_RenderClear(renderer);
        if (backdrop) {
            SDL_RenderTexture(renderer, backdrop.get(), nullptr, nullptr);
            ink.box(0, 0, 1280, 720, {9, 15, 22, 198});
        }
        if (linyuan) {
            ink.box(108, 78, 1064, 540, {13, 21, 28, 226});
            ink.box(108, 78, 1064, 3, gold);
            ink.box(108, 616, 1064, 2, {204, 158, 86, 130});
        }
        ink.text(160, 108, 26, stage.heading, gold);
        ink.text(160, 173, 48, linyuan ? "本章御剑已毕" : "本章巡灯已毕", ivory);
        ink.text(990, 160, 90, score.grade(), gold, true);
        ink.text(162, 310, 27, "得分    " + std::to_string(score.points), ivory);
        ink.text(630, 310, 27, "命中率    " + std::to_string(accuracy) + "%", ivory);
        ink.text(162, 382, 27, "最高连击    " + std::to_string(score.combo), ivory);
        ink.text(630, 382, 27, "受伤    " + std::to_string(score.damage) + " 次", ivory);
        ink.text(162, 454, 27, (linyuan ? "击毁机关    " : "净化灯妖    ") + std::to_string(score.purified), ivory);
        if (linyuan) {
            ink.text(630, 454, 24, "玄武渡江  ·  第二章 天机峰  敬请期待", gold);
            ink.text(640, 560, 21, "已存档　·　点击或按 Enter 返回", ivory, true);
        } else {
            ink.text(640, 610, 21, "已存档　·　点击或按 Enter 继续", gold, true);
        }
        if (receiver)
            drawGunBorder(ink);
        CampaignRecording::frame(renderer);
        SDL_RenderPresent(renderer);
        if (automated && (!CampaignRecording::enabled() || SDL_GetTicks() - entered >= 1600))
            return true;
        bool next = false;
        if (receiver)
            receiver->poll(SDL_GetTicks(),
                           [&](RemoteAction a, Point) { next |= a == RemoteAction::start; });
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_EVENT_QUIT ||
                (event.type == SDL_EVENT_KEY_DOWN && event.key.key == SDLK_ESCAPE))
                return false;
            if (event.type == SDL_EVENT_KEY_DOWN && !event.key.repeat &&
                (event.key.key == SDLK_RETURN || event.key.key == SDLK_SPACE))
                next = true;
            if (event.type == SDL_EVENT_MOUSE_BUTTON_DOWN && event.button.button == SDL_BUTTON_LEFT)
                next = true;
        }
        if (next)
            return true;
        SDL_Delay(16);
    }
}

MenuChoice campaignMenu(SDL_Renderer *renderer, const Campaign &campaign, Progress &state,
                        Receiver *receiver, bool automated, ScoreAudio *music) {
    Ink ink(renderer);
    const bool complete = state.next == "@complete";
    const bool resume = !state.next.empty() && !complete;
    std::string nextDifficulty = state.difficulty;
    auto selectDifficulty = [&](std::string value) {
        nextDifficulty = std::move(value);
        state.difficulty = nextDifficulty;
        if (resume && state.lives > 0)
            state.lives = nextDifficulty == "easy" ? std::max(state.lives, 5) : std::min(state.lives, 3);
    };
    auto newGame = [&] {
        state.difficulty = nextDifficulty;
        return MenuChoice::newGame;
    };
    const auto automaticChoice = complete ? MenuChoice::quit
                                 : resume ? MenuChoice::resume
                                          : MenuChoice::newGame;
    if (automated && !CampaignRecording::enabled())
        return automaticChoice;
    const auto entered = SDL_GetTicks();
    ChapterScore total;
    Texture backdrop(nullptr, SDL_DestroyTexture);
    if (fs::is_regular_file(campaign.titleArt)) {
        const auto name = campaign.titleArt.u8string();
        std::unique_ptr<SDL_Surface, decltype(&SDL_DestroySurface)> art(
            SDL_LoadBMP(reinterpret_cast<const char *>(name.c_str())), SDL_DestroySurface);
        if (art)
            backdrop.reset(SDL_CreateTextureFromSurface(renderer, art.get()));
    }
    for (auto &[id, score] : state.scores)
        total.add(score);
    struct StageShortcut {
        const char *id;
        const char *label;
        float x;
        SDL_Keycode key;
    };
    std::vector<StageShortcut> shortcuts;
    if (campaign.linyuan && campaign.stages.size() > 6) {
        const struct {
            const char *id;
            const char *label;
            SDL_Keycode key;
        } wants[] = {
            {"dukou_card", "F1 集市", SDLK_F1},
            {"bamboo_card", "F2 竹海", SDLK_F2},
            {"shoal_card", "F3 饕餮", SDLK_F3},
        };
        float sx = 108.f;
        for (const auto &w : wants) {
            if (std::any_of(campaign.stages.begin(), campaign.stages.end(),
                            [&](const Stage &s) { return s.id == w.id; })) {
                shortcuts.push_back({w.id, w.label, sx, w.key});
                sx += 154.f;
            }
        }
    }
    auto jumpStage = [&](const char *stageId) {
        state.difficulty = nextDifficulty;
        state.scores.clear();
        state.lastStoryCivilian = false;
        state.next = stageId;
        state.lives = difficulty(state.difficulty).lives;
        state.arrows = 8;
        state.reloadRemaining = 0;
        // Pre-seed Sword Intent on Taotie shortcut so 万剑归宗 becomes reachable in Boss Phase 3.
        state.energy = std::string(stageId) == "shoal_card"
                           ? (state.difficulty == "easy" ? 9 : state.difficulty == "hard" ? 16 : 12)
                           : 0;
        return MenuChoice::resume;
    };
    Point hover{-1, -1};
    auto inRect = [](Point p, float x, float y, float w, float h) {
        return p.x >= x && p.x <= x + w && p.y >= y && p.y <= y + h;
    };
    for (;;) {
        if (music) {
            music->volume(state.musicVolume / 100.f, state.effectsVolume / 100.f);
            music->update(true);
        }
        SDL_SetRenderDrawColor(renderer, 16, 23, 31, 255);
        SDL_RenderClear(renderer);
        if (backdrop) {
            SDL_RenderTexture(renderer, backdrop.get(), nullptr, nullptr);
            ink.box(0, 0, 1280, 720, {8, 14, 23, 156});
            ink.box(0, 0, 595, 720, {8, 14, 23, 96});
        }
        ink.text(110, 68, 22,
                 complete ? (campaign.linyuan ? "临渊御剑录" : "上元灯记")
                          : campaign.stages[campaign.locate(state.next)].heading,
                 gold);
        ink.text(106, 110, 62, campaign.title, ivory);
        if (complete) {
            ink.text(110, 204, 25, "总评 " + total.grade() + "     得分 " + std::to_string(total.points),
                     gold);
        } else if (resume) {
            ink.text(110, 206, 22, "已存至  " + campaign.stages[campaign.locate(state.next)].heading,
                     ivory);
        } else if (campaign.linyuan) {
            ink.text(110, 208, 19, "左键出剑 · 右键或 R 收剑 · 空格或中键万剑归宗", ivory);
        }
        const bool startHover = inRect(hover, 108, 258, 376, 54);
        ink.box(108, 258, 376, 54, startHover ? SDL_Color{224, 176, 98, 255} : SDL_Color{204, 158, 86, 255});
        ink.text(296, 272, 24,
                 resume ? (campaign.linyuan ? "继续御剑" : "继续巡灯")
                        : (campaign.linyuan ? "开始御剑" : "从上元夜开始"),
                 dark, true);
        if (resume) {
            const bool restartHover = inRect(hover, 108, 324, 240, 38);
            ink.box(108, 324, 240, 38,
                    restartHover ? SDL_Color{34, 48, 60, 235} : SDL_Color{18, 28, 38, 210});
            ink.box(108, 324, 3, 38, gold);
            ink.text(228, 332, 18, "N   从头开始", ivory, true);
        }

        // Three directly clickable difficulty cards cleanly housed in left column.
        ink.text(110, 378, 17, "选择难度（1 / 2 / 3 或点击 · 即时生效）", gold);
        struct DiffCard {
            const char *id;
            const char *title;
            const char *hint;
            float x;
        };
        const DiffCard cards[] = {
            {"easy", "1 简单", "5 剑穗 · 宽松时机 · 百姓免扣命", 108.f},
            {"normal", "2 普通", "3 剑穗 · 标准时机 · 推荐体验", 262.f},
            {"hard", "3 困难", "3 剑穗 · 极速破绽 · 饕餮四重核心", 416.f},
        };
        const char *activeHint = cards[1].hint;
        for (const auto &card : cards) {
            const bool active = nextDifficulty == card.id;
            const bool hovered = inRect(hover, card.x, 406, 142, 48);
            if (active)
                activeHint = card.hint;
            const SDL_Color bg = active    ? SDL_Color{204, 158, 86, 250}
                                 : hovered ? SDL_Color{38, 52, 66, 235}
                                           : SDL_Color{18, 28, 38, 218};
            ink.box(card.x, 406, 142, 48, bg);
            if (active)
                ink.box(card.x, 450, 142, 4, {255, 228, 156, 255});
            else
                ink.box(card.x, 406, 3, 48, {136, 114, 80, 210});
            ink.text(card.x + 71, 418, 20, card.title, active ? dark : ivory, true);
        }
        ink.text(110, 464, 17, activeHint, ivory);

        if (!shortcuts.empty()) {
            ink.text(110, 504, 17, "关卡直达（F1 / F2 / F3 或点击重温试炼）", gold);
            for (const auto &sc : shortcuts) {
                const bool hov = inRect(hover, sc.x, 532, 142, 40);
                ink.box(sc.x, 532, 142, 40, hov ? SDL_Color{38, 52, 66, 235} : SDL_Color{18, 28, 38, 218});
                ink.box(sc.x, 532, 3, 40, gold);
                ink.text(sc.x + 71, 542, 18, sc.label, ivory, true);
            }
        }

        // Bottom settings bar below artwork silhouettes.
        ink.box(96, 628, 1088, 46, {10, 16, 24, 204});
        ink.box(96, 628, 1088, 2, {136, 114, 80, 120});
        ink.text(120, 640, 18, state.subtitles ? "V  字幕开启" : "V  字幕关闭", ivory);
        ink.text(440, 640, 18, "M  配乐 " + std::to_string(state.musicVolume) + "%", ivory);
        ink.text(700, 640, 18, "F  音效 " + std::to_string(state.effectsVolume) + "%", ivory);
        ink.text(960, 640, 18, "G  对白 " + std::to_string(state.voiceVolume) + "%", ivory);
        if (receiver)
            drawGunBorder(ink);
        CampaignRecording::frame(renderer);
        SDL_RenderPresent(renderer);
        if (automated && SDL_GetTicks() - entered >= (complete ? 3000u : 1800u))
            return automaticChoice;
        bool start = false;
        if (receiver)
            receiver->poll(SDL_GetTicks(),
                           [&](RemoteAction action, Point) { start |= action == RemoteAction::start; });
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN &&
                (e.gbutton.button == SDL_GAMEPAD_BUTTON_SOUTH || e.gbutton.button == SDL_GAMEPAD_BUTTON_START))
                start = true;
            if (e.type == SDL_EVENT_QUIT)
                return MenuChoice::quit;
            if (e.type == SDL_EVENT_MOUSE_MOTION) {
                SDL_ConvertEventToRenderCoordinates(renderer, &e);
                hover = {e.motion.x, e.motion.y};
            }
            if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {
                const auto key = e.key.key;
                if (key == SDLK_ESCAPE)
                    return MenuChoice::quit;
                if (key == SDLK_N)
                    return newGame();
                if (key == SDLK_RETURN)
                    start = true;
                if (key == SDLK_V)
                    state.subtitles = !state.subtitles;
                if (key == SDLK_M)
                    state.musicVolume = (state.musicVolume + 20) % 120;
                if (key == SDLK_F)
                    state.effectsVolume = (state.effectsVolume + 20) % 120;
                if (key == SDLK_G)
                    state.voiceVolume = (state.voiceVolume + 20) % 120;
                if (key >= SDLK_1 && key <= SDLK_3)
                    selectDifficulty(key == SDLK_1 ? "easy" : key == SDLK_2 ? "normal" : "hard");
                for (const auto &sc : shortcuts)
                    if (key == sc.key)
                        return jumpStage(sc.id);
            }
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button == SDL_BUTTON_LEFT) {
                SDL_ConvertEventToRenderCoordinates(renderer, &e);
                const Point click{e.button.x, e.button.y};
                if (inRect(click, 96, 628, 1088, 46)) {
                    if (click.x < 380)
                        state.subtitles = !state.subtitles;
                    else if (click.x < 640)
                        state.musicVolume = (state.musicVolume + 20) % 120;
                    else if (click.x < 900)
                        state.effectsVolume = (state.effectsVolume + 20) % 120;
                    else
                        state.voiceVolume = (state.voiceVolume + 20) % 120;
                }
                for (const auto &sc : shortcuts) {
                    if (inRect(click, sc.x, 532, 142, 40))
                        return jumpStage(sc.id);
                }
                for (const auto &card : cards) {
                    if (inRect(click, card.x, 406, 142, 48))
                        selectDifficulty(card.id);
                }
                if (inRect(click, 108, 258, 376, 54))
                    start = true;
                if (resume && inRect(click, 108, 324, 240, 38))
                    return newGame();
            }
        }
        if (start)
            return resume ? MenuChoice::resume : newGame();
        SDL_Delay(16);
    }
}
} // namespace ca
