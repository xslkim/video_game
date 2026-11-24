#include "changan_story.hpp"
#include "changan_record.hpp"
#include "sound.hpp"
#include "ui.hpp"
#include <deque>
#include <fstream>
#include <windows.h>

namespace ca {
using Texture = std::unique_ptr<SDL_Texture, decltype(&SDL_DestroyTexture)>;
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
    CampaignRecording::Audio recorded(sound, 60);
    ScoreAudio localFoley;
    if (!score && (choice || travel.arrows)) {
        localFoley.open(sound.device(), media.parent_path() / "audio", false);
        localFoley.volume(0.f, effectsGain);
    }
    ScoreAudio &foley = score ? *score : localFoley;
    std::unique_ptr<SDL_AudioStream, decltype(&SDL_DestroyAudioStream)> dialogue(nullptr,
                                                                                 SDL_DestroyAudioStream);
    if (!film.voice.empty() && sound.device()) {
        const auto file = (media.parent_path() / "audio/voice" / (film.voice + ".wav")).u8string();
        SDL_AudioSpec format{};
        Uint8 *pcm = nullptr;
        Uint32 bytes = 0;
        if (!SDL_LoadWAV(reinterpret_cast<const char *>(file.c_str()), &format, &pcm, &bytes))
            throw std::runtime_error("Missing dialogue: " + film.voice);
        std::unique_ptr<Uint8, decltype(&SDL_free)> owner(pcm, SDL_free);
        dialogue.reset(SDL_CreateAudioStream(&format, &format));
        if (!dialogue || !SDL_BindAudioStream(sound.device(), dialogue.get()) ||
            !SDL_SetAudioStreamGain(dialogue.get(), voiceGain) ||
            !SDL_PutAudioStreamData(dialogue.get(), pcm, bytes) || !SDL_FlushAudioStream(dialogue.get()))
            throw std::runtime_error(SDL_GetError());
    }
    Ink ink(renderer);
    Texture texture(
        SDL_CreateTexture(renderer, SDL_PIXELFORMAT_IYUV, SDL_TEXTUREACCESS_STREAMING, 1280, 720),
        SDL_DestroyTexture);
    if (!texture)
        throw std::runtime_error(SDL_GetError());
    auto now = [] { return SDL_GetTicksNS() / 1e9; };
    int displayed = -1;
    Point aim{-1, -1};
    uint64_t submitted = 0;
    std::deque<std::pair<uint64_t, int>> history;
    bool paused = false;
    bool skipSent = false;
    double localReload = 0, previous = now();
    double &reloadLeft = travel.remaining ? *travel.remaining : localReload;
    int *arrows = choice ? &choice->ammo : travel.arrows;
    double exposedLeft = 0;
    double effectTime = 0, effectAt = -1;
    Point effectPoint{};
    sound.begin(movie, 0, 1., now());
    sound.clipGain(film.take == "aying_help" ? voiceGain : effectsGain);
    auto pause = [&](bool yes) {
        paused = yes;
        sound.pause(yes, now());
    };
    for (;;) {
        bool skip = false;
        auto fire = [&](Point p, uint64_t when) {
            if (!choice || paused || choice->fired ||
                (!choice->story && (choice->ammo == 0 || reloadLeft > 0)))
                return;
            auto shown = std::find_if(history.rbegin(), history.rend(),
                                      [&](auto entry) { return entry.first <= when; });
            if (shown == history.rend() || shown->second < choice->begin || shown->second >= choice->end)
                return;
            if (effectAt >= 0 && effectTime - effectAt < .15)
                return;
            choice->fired = true;
            choice->hitFrame = shown->second;
            if (!choice->story)
                --choice->ammo;
            foley.cue("shot");
            effectAt = effectTime;
            effectPoint = p;
            choice->selected = "miss";
            for (const auto &region : choice->regions) {
                if (!region.covers(shown->second, p))
                    continue;
                choice->selected = region.id;
                break;
            }
            if (choice->selected == "miss" && choice->assist) {
                for (const auto &region : choice->regions) {
                    if (std::find(choice->eligible.begin(), choice->eligible.end(), region.id) ==
                        choice->eligible.end())
                        continue;
                    if (region.covers(shown->second, p, choice->assist)) {
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
                reloadLeft = choice ? choice->reloadDuration : travel.duration;
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
            if (e.type == SDL_EVENT_QUIT)
                return FilmEnd::quit;
            if (e.type == SDL_EVENT_WINDOW_FOCUS_LOST && !automated)
                pause(true);
            if (e.type == SDL_EVENT_KEY_DOWN && !e.key.repeat) {
                if (e.key.key == SDLK_ESCAPE || (paused && e.key.key == SDLK_RETURN))
                    pause(!paused);
                else if (choice && e.key.key == SDLK_SPACE)
                    expose();
                else if (e.key.key == SDLK_SPACE || e.key.key == SDLK_RETURN)
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
                else if (e.button.x > 1050 && e.button.y > 635)
                    skip = true;
            }
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button == SDL_BUTTON_RIGHT)
                reload();
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button == SDL_BUTTON_MIDDLE)
                expose();
        }
        if (choice && choice->fired && !paused && effectTime - effectAt >= .29)
            return FilmEnd::selected;
        if (choice && !choice->fired && !paused &&
            (displayed >= choice->end || (choice->exposed && exposedLeft <= 0)))
            return FilmEnd::expired;
        if (skip && !choice && !paused)
            return FilmEnd::skipped;
        const int frame = sound.localFrame(now());
        if (score)
            score->update(!paused);
        if (frame >= film.frames && !paused && displayed == film.frames - 1 &&
            (!dialogue || SDL_GetAudioStreamQueued(dialogue.get()) == 0))
            return FilmEnd::finished;
        const int shown = std::clamp(frame, 0, film.frames - 1);
        if (shown != displayed) {
            const auto *pic = movie.at(shown);
            if (!SDL_UpdateYUVTexture(texture.get(), nullptr, pic->data[0], pic->linesize[0], pic->data[1],
                                      pic->linesize[1], pic->data[2], pic->linesize[2]))
                throw std::runtime_error(SDL_GetError());
            displayed = shown;
        }
        SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
        SDL_RenderClear(renderer);
        SDL_RenderTexture(renderer, texture.get(), nullptr, nullptr);
        if (receiver)
            drawGunBorder(ink);
        const double age = effectTime - effectAt;
        if (choice && effectAt >= 0 && age < .29) {
            const auto a = Uint8(230 * (1. - age / .29));
            ink.ring(effectPoint, int(8 + 74 * age), {255, 213, 125, a});
            for (int i = 0; i < 10; ++i) {
                const double angle = i * .62831853;
                const float x = float(effectPoint.x + (11 + 120 * age) * std::cos(angle));
                const float y = float(effectPoint.y + (11 + 120 * age) * std::sin(angle));
                ink.box(x, y, 3, 3, {255, 235, 167, a});
            }
        }
        if (subtitles && !film.subtitle.empty() && displayed >= 5 &&
            (!choice || displayed < choice->begin)) {
            ink.box(100, 622, 1080, 52, {9, 12, 20, 185});
            ink.text(640, 632, 25, film.subtitle, ivory, true);
        }
        if (choice && displayed >= choice->begin && displayed < choice->end) {
            ink.box(250, 610, 780, 54, {9, 12, 20, 196});
            ink.text(640, 625, 23, choice->prompt, gold, true);
            if (choice->strength > 1)
                ink.text(640, 577, 20,
                         "符印  " + std::to_string(choice->partialHits + choice->specialDamage) + " / " +
                             std::to_string(choice->strength),
                         ivory, true);
            if (aim.x >= 0)
                ink.ring(aim, 9, ivory);
            if (choice->regions.size() == 1 || choice->highlight || choice->exposed) {
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
                    ink.ring(center, 30, gold);
                }
            }
        } else if (!choice) {
            ink.box(1080, 674, 187, 36, {9, 12, 20, 175});
            ink.text(1173, 680, 17, paused ? "点击继续" : "空格  跳过本段", ivory, true);
        }
        if (choice && !choice->story) {
            ink.box(26, 24, 346, 52, {9, 12, 20, 185});
            ink.text(44, 38, 20,
                     "生命 " + std::to_string(choice->lives) + "     " +
                         (reloadLeft > 0 ? "更换符匣" : "符箭 " + std::to_string(choice->ammo) + " / 8"),
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
        if (choice && automated && !choice->replayAnswer.empty() && !choice->fired &&
            displayed >= choice->begin + 3 && displayed < choice->end) {
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
Campaign::Campaign(const fs::path &root, const std::string &name) {
    auto checkId = [](const std::string &id) {
        if (id.empty() ||
            id.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_") != std::string::npos)
            throw std::runtime_error("Invalid campaign identifier: " + id);
    };
    checkId(name);
    const auto data = Json::parse(std::ifstream(root / "worlds/changan" / (name + ".json")));
    const auto media = Json::parse(std::ifstream(root / "worlds/changan/drama.json"));
    title = data.at("title");
    titleArt = root / "assets/changan/title.bmp";
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
            stage.music = item.value("music", "");
            if (!stage.music.empty())
                checkId(stage.music);
            checkId(stage.id);
            if (!ids.insert(stage.id).second)
                throw std::runtime_error("Duplicate stage: " + stage.id);
            if (item.at("type") == "encounter") {
                stage.level = item.at("level");
                checkId(stage.level);
                if (!fs::is_regular_file(root / "worlds/changan" / stage.level / "level.json"))
                    throw std::runtime_error("Missing playable stage: " + stage.level);
            } else if (item.at("type") == "film") {
                for (const auto &shot : item.at("takes")) {
                    const std::string take = shot.at("id");
                    checkId(take);
                    const int count = media.at(take).at("frames");
                    if (count <= 0 || !fs::is_regular_file(root / "assets/changan/drama" / (take + ".mp4")))
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
                }
                if (stage.films.empty())
                    throw std::runtime_error("Empty cinematic: " + stage.id);
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

FilmEnd playTrial(SDL_Window *window, SDL_Renderer *renderer, const fs::path &root, const Stage &stage,
                  Progress &state, Receiver *gun, bool automated, const fs::path &evidence,
                  const std::string &scenario, ScoreAudio *score, int &completedReloads) {
    const auto index = Json::parse(std::ifstream(root / "worlds/changan/drama.json"));
    auto film = [&](const std::string &id) { return Film{id, "", index.at(id).at("frames")}; };
    const auto media = root / "assets/changan/drama";
    const auto &trial = stage.trial;
    std::string step = trial.at("first");
    ChapterScore section;
    int lives = state.lives, energy = state.energy, ammo = state.arrows, combo = 0;
    int visits = 0;
    bool safeRescue = true;
    int retries = 0;
    Json trace = Json::array();
    while (step != "@complete") {
        if (automated && ++visits > 150)
            throw std::runtime_error("Trial replay did not converge: " + stage.id);
        const auto &record = trial.at("steps").at(step);
        const std::string take = record.at("take");
        Film movie = film(take);
        movie.voice = record.value("voice", "");
        movie.subtitle = record.value("subtitle", "");
        const auto annotation =
            Json::parse(std::ifstream(root / "worlds/changan/regions" / (take + ".json")));
        if (annotation.at("sha256") != index.at(take).at("sha256"))
            throw std::runtime_error("Outdated story region: " + take);
        const auto &windowFrames = record.at("window");
        int start = windowFrames.at(0);
        int length = windowFrames.at(1);
        const bool storyShot = record.value("story_shot", false);
        if (storyShot)
            length = state.difficulty == "easy" ? 72 : state.difficulty == "hard" ? 29 : 48;
        else {
            const bool flight = record.value("projectile", false);
            const double scale = state.difficulty == "easy"   ? (flight ? 1.3 : 1.4)
                                 : state.difficulty == "hard" ? (flight ? .7 : .65)
                                                              : 1.;
            length = std::min(movie.frames - start - 1, int(std::lround(length * scale)));
        }
        FilmChoice target{start, start + length, record.at("prompt"), record.at("answer")};
        target.replayAnswer = target.answer;
        target.assist = state.difficulty == "easy" ? 24 : state.difficulty == "hard" ? 0 : 12;
        target.story = storyShot;
        target.strength = record.value("strength", 1);
        if (target.strength < 1 || target.strength > 6 || (storyShot && target.strength != 1))
            throw std::runtime_error("Invalid target strength: " + step);
        target.ammo = ammo;
        target.lives = lives;
        target.highlight = record.value("highlight", false);
        target.guards = record.value("guards", std::vector<std::string>{});
        const int capacity = state.difficulty == "easy" ? 15 : state.difficulty == "hard" ? 25 : 20;
        target.canExpose = record.value("expose", false) && energy == capacity;
        target.canStrike = record.value("thunder_strike", false) && !target.canExpose && energy == capacity;
        target.autoSpecial = scenario == "boss-thunder";
        target.reloadDuration = state.difficulty == "easy" ? .4 : state.difficulty == "hard" ? .8 : .6;
        if (start < 0 || length <= 0 || target.end >= movie.frames)
            throw std::runtime_error("Invalid story window: " + step);
        for (const auto &key : record.at("zones")) {
            TrackedRegion region{key};
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
        if (storyShot && scenario == "story-miss")
            target.replayAnswer = "miss";
        if (storyShot && scenario == "story-timeout")
            target.replayAnswer.clear();
        if (stage.id == "hall_of_mirrors" && step == "three" && scenario == "mirror-right")
            target.replayAnswer = "right";
        if (stage.id == "nine_lanterns" && step == "signal_1" && trace.empty() &&
            scenario == "dragon-order")
            target.replayAnswer = "head_3";
        if (stage.id == "west_possessions" && scenario == "civilian-retry" && retries == 0)
            target.replayAnswer = "civilian";
        auto result = playFilm(window, renderer, media, movie, state.subtitles, gun, automated, &target,
                               score, state.voiceVolume / 100.f, state.effectsVolume / 100.f,
                               {&ammo, &state.reloadRemaining, target.reloadDuration, &completedReloads});
        if (result == FilmEnd::quit)
            return result;
        const auto key = target.fired ? target.selected : std::string("timeout");
        const auto &branch = record.at("outcomes").at(key);
        const bool civilian = branch.value("civilian", false);
        const int baseAward = branch.value("points", 0);
        int award = civilian ? -100 : baseAward;
        if (!storyShot && award > 0 && branch.value("purified", 0) > 0 && !target.specialFinish) {
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
        if (score) {
            if (civilian)
                score->cue("civilian");
            else if (harm)
                score->cue("hurt");
            else if (award > 0 && record.value("projectile", false))
                score->cue("intercept");
            else if (branch.value("purified", 0) > 0)
                score->cue("purify");
        }
        ammo = target.ammo;
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
        section.hits += target.fired && award > 0 && !target.specialFinish;
        section.points += award;
        section.points = std::max(-state.scores[stage.chapter].points, section.points);
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
                         {"damage", harm},
                         {"special", target.spent},
                         {"attempt", retries + 1},
                         {"response", branch.value("response", "")}});
        if (lives <= 0) {
            if (!automated) {
                SDL_MessageBoxButtonData options[] = {
                    {SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT, 1, "重试此段"},
                    {SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT, 0, "结束游戏"}};
                SDL_MessageBoxData box{SDL_MESSAGEBOX_INFORMATION,
                                       window,
                                       "灯火未平",
                                       "灯火熄灭。要重新尝试这一段吗？",
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
            ++retries;
            lives = state.difficulty == "easy" ? 5 : 3;
            energy = combo = 0;
            ammo = 8;
            step = trial.at("first");
            continue;
        }
        if (branch.contains("response")) {
            auto response = film(branch.at("response"));
            if (playFilm(window, renderer, media, response, state.subtitles, gun, automated, nullptr, score,
                         state.voiceVolume / 100.f, state.effectsVolume / 100.f,
                         {&ammo, &state.reloadRemaining, target.reloadDuration, &completedReloads}) ==
                FilmEnd::quit)
                return FilmEnd::quit;
        }
        step = branch.at("next");
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
                    Receiver *receiver, bool automated, ScoreAudio *music) {
    Ink ink(renderer);
    const auto accuracy = score.shots ? std::lround(100. * score.hits / score.shots) : 0;
    const auto entered = SDL_GetTicks();
    for (;;) {
        if (music)
            music->update(true);
        SDL_SetRenderDrawColor(renderer, 16, 23, 31, 255);
        SDL_RenderClear(renderer);
        ink.text(160, 108, 26, stage.heading, gold);
        ink.text(160, 173, 48, "本章巡灯已毕", ivory);
        ink.text(990, 160, 90, score.grade(), gold, true);
        ink.text(162, 310, 27, "得分    " + std::to_string(score.points), ivory);
        ink.text(630, 310, 27, "命中率    " + std::to_string(accuracy) + "%", ivory);
        ink.text(162, 382, 27, "最高连击    " + std::to_string(score.combo), ivory);
        ink.text(630, 382, 27, "受伤    " + std::to_string(score.damage) + " 次", ivory);
        ink.text(162, 454, 27, "净化灯妖    " + std::to_string(score.purified), ivory);
        ink.text(640, 610, 21, "已存档　·　点击或按 Enter 继续", gold, true);
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
        if (!resume)
            state.difficulty = nextDifficulty;
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
    for (;;) {
        if (music) {
            music->volume(state.musicVolume / 100.f, state.effectsVolume / 100.f);
            music->update(true);
        }
        SDL_SetRenderDrawColor(renderer, 16, 23, 31, 255);
        SDL_RenderClear(renderer);
        if (backdrop) {
            SDL_RenderTexture(renderer, backdrop.get(), nullptr, nullptr);
            ink.box(0, 0, 1280, 720, {8, 14, 23, 166});
        }
        ink.text(110, 85, 23, complete ? "上元灯记" : campaign.stages[campaign.locate(state.next)].heading,
                 gold);
        ink.text(106, 142, 68, campaign.title, ivory);
        if (complete) {
            ink.text(110, 256, 27, "总评 " + total.grade() + "     得分 " + std::to_string(total.points),
                     gold);
            int row = 0;
            for (const auto &stage : campaign.stages) {
                auto found = state.scores.find(stage.chapter);
                if (found == state.scores.end() ||
                    stage.id !=
                        std::find_if(campaign.stages.begin(), campaign.stages.end(), [&](const Stage &s) {
                            return s.chapter == stage.chapter;
                        })->id)
                    continue;
                ink.text(735, 190.f + 43.f * row++, 21, stage.heading + "    " + found->second.grade(),
                         ivory);
            }
        } else if (resume) {
            ink.text(110, 256, 24, "已存至  " + campaign.stages[campaign.locate(state.next)].heading,
                     ivory);
        }
        ink.box(108, 352, 375, 61, {204, 158, 86, 255});
        ink.text(296, 368, 25, resume ? "继续巡灯" : "从上元夜开始", dark, true);
        if (resume)
            ink.text(112, 432, 21, "N   重新开始", ivory);
        ink.text(112, 526, 20,
                 std::string(resume ? "新局难度   " : "难度   ") +
                     std::string(nextDifficulty == "easy"     ? "简单"
                                 : nextDifficulty == "normal" ? "普通"
                                                              : "困难"),
                 gold);
        ink.text(112, 568, 18, resume ? "1 / 2 / 3 选新局难度，续关沿用存档" : "1 简单    2 普通    3 困难",
                 ivory);
        ink.text(112, 614, 18, state.subtitles ? "V   字幕开启" : "V   字幕关闭", ivory);
        ink.text(725, 525, 19, "M　配乐  " + std::to_string(state.musicVolume) + "%", ivory);
        ink.text(725, 568, 19, "F　音效  " + std::to_string(state.effectsVolume) + "%", ivory);
        ink.text(725, 612, 19, "G　对白  " + std::to_string(state.voiceVolume) + "%", ivory);
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
            if (e.type == SDL_EVENT_QUIT)
                return MenuChoice::quit;
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
            }
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN && e.button.button == SDL_BUTTON_LEFT) {
                SDL_ConvertEventToRenderCoordinates(renderer, &e);
                if (e.button.x >= 710 && e.button.x <= 1050) {
                    if (e.button.y >= 510 && e.button.y < 553)
                        state.musicVolume = (state.musicVolume + 20) % 120;
                    if (e.button.y >= 553 && e.button.y < 596)
                        state.effectsVolume = (state.effectsVolume + 20) % 120;
                    if (e.button.y >= 596 && e.button.y < 645)
                        state.voiceVolume = (state.voiceVolume + 20) % 120;
                }
                if (e.button.x >= 108 && e.button.x <= 485) {
                    if (e.button.y >= 352 && e.button.y <= 413)
                        start = true;
                    if (resume && e.button.y >= 425 && e.button.y <= 470)
                        return newGame();
                    if (e.button.y >= 604 && e.button.y <= 655)
                        state.subtitles = !state.subtitles;
                    if (e.button.y >= 516 && e.button.y <= 595)
                        selectDifficulty(nextDifficulty == "easy"     ? "normal"
                                         : nextDifficulty == "normal" ? "hard"
                                                                      : "easy");
                }
            }
        }
        if (start)
            return resume ? MenuChoice::resume : newGame();
        SDL_Delay(16);
    }
}
} // namespace ca
