#pragma once
#include "sound.hpp"
#include <condition_variable>
#include <deque>
#include <fstream>
#include <mutex>
#include <thread>

namespace ca {
using namespace dc;

// The offline recorder samples the same rendered surface and audio devices
// heard during play. Timestamps include real decoder and loading delays.
class CampaignRecording {
    using Surface = std::unique_ptr<SDL_Surface, decltype(&SDL_DestroySurface)>;
    inline static CampaignRecording *active = nullptr;
    fs::path folder;
    std::ofstream frames;
    double next = 0;
    int number = 0, streams = 0;
    std::string failure;
    std::mutex mutex;
    std::condition_variable ready;
    std::deque<std::pair<fs::path, Surface>> pending;
    std::thread writer;
    bool stopping = false;
    std::string writeError;
    void saveFrames() {
        for (;;) {
            std::unique_lock lock(mutex);
            ready.wait(lock, [&] { return stopping || !pending.empty(); });
            if (pending.empty())
                return;
            auto [path, surface] = std::move(pending.front());
            pending.pop_front();
            lock.unlock();
            const auto name = path.u8string();
            if (!SDL_SaveBMP(surface.get(), reinterpret_cast<const char *>(name.c_str()))) {
                std::lock_guard guard(mutex);
                writeError = SDL_GetError();
                return;
            }
        }
    }
    void drain() {
        {
            std::lock_guard lock(mutex);
            stopping = true;
        }
        ready.notify_one();
        if (writer.joinable())
            writer.join();
    }
    static double now() { return SDL_GetTicksNS() / 1e9; }

  public:
    const double begun = now();
    explicit CampaignRecording(const fs::path &path) : folder(path) {
        if (!fs::create_directories(folder / "frames"))
            throw std::runtime_error("Recording needs a fresh directory");
        frames.open(folder / "frames.tsv");
        frames.exceptions(std::ios::badbit | std::ios::failbit);
        frames.precision(12);
        writer = std::thread([this] { saveFrames(); });
        active = this;
    }
    ~CampaignRecording() {
        active = nullptr;
        drain();
    }
    static bool enabled() { return active != nullptr; }
    static void frame(SDL_Renderer *renderer) {
        auto *r = active;
        const auto requested = now();
        if (!r || requested < r->next)
            return;
        {
            std::lock_guard lock(r->mutex);
            if (!r->writeError.empty())
                throw std::runtime_error(r->writeError);
            if (r->pending.size() >= 6)
                return;
        }
        Surface src(SDL_RenderReadPixels(renderer, nullptr), SDL_DestroySurface);
        if (!src)
            throw std::runtime_error(SDL_GetError());
        Surface small(SDL_ScaleSurface(src.get(), 960, 540, SDL_SCALEMODE_LINEAR), SDL_DestroySurface);
        if (!small)
            throw std::runtime_error(SDL_GetError());
        {
            std::lock_guard lock(r->mutex);
            r->pending.emplace_back(r->folder / "frames" / (std::to_string(r->number) + ".bmp"),
                                    std::move(small));
        }
        r->ready.notify_one();
        const double presented = now();
        r->frames << r->number++ << '\t' << presented - r->begun << '\n';
        r->next = requested + 1. / 24.;
    }
    class Audio {
        CampaignRecording *rec = active;
        Sound &sound;
        fs::path path;

      public:
        explicit Audio(Sound &s, int limit) : sound(s) {
            if (!rec)
                return;
            path = rec->folder / "audio" / std::to_string(rec->streams++);
            fs::create_directories(path);
            sound.startCapture(limit);
        }
        ~Audio() {
            if (!rec)
                return;
            try {
                sound.finishCapture(path, rec->begun);
            } catch (const std::exception &e) {
                rec->failure = e.what();
            }
        }
    };
    void finish() {
        drain();
        if (!writeError.empty())
            throw std::runtime_error(writeError);
        if (!failure.empty())
            throw std::runtime_error(failure);
        frames.flush();
        std::ofstream(folder / "recording.json")
            << Json{{"seconds", now() - begun}, {"frames", number}, {"streams", streams}}.dump(2);
    }
};
} // namespace ca
