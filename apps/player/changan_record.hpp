#pragma once
#include "sound.hpp"
#include <condition_variable>
#include <deque>
#include <fstream>
#include <mutex>
#include <thread>

namespace ca {
using namespace dc;

// SDL render readback stays on the render thread. CPU scaling and file writes
// use a bounded worker queue so a slow disk cannot stall play or consume all RAM.
class FrameWriter {
    using Surface = std::unique_ptr<SDL_Surface, decltype(&SDL_DestroySurface)>;
    int width, height;
    std::mutex mutex;
    std::condition_variable ready;
    std::deque<std::pair<fs::path, Surface>> pending;
    bool stopping = false;
    std::string writeError;
    std::thread writer;
    void saveFrames() {
        for (;;) {
            std::unique_lock lock(mutex);
            ready.wait(lock, [&] { return stopping || !pending.empty(); });
            if (pending.empty())
                return;
            auto [path, surface] = std::move(pending.front());
            pending.pop_front();
            lock.unlock();
            if (width > 0 && (width != surface->w || height != surface->h))
                surface.reset(SDL_ScaleSurface(surface.get(), width, height, SDL_SCALEMODE_LINEAR));
            const auto name = path.u8string();
            if (!surface || !SDL_SaveBMP(surface.get(), reinterpret_cast<const char *>(name.c_str()))) {
                std::lock_guard guard(mutex);
                writeError = SDL_GetError();
                return;
            }
        }
    }
  public:
    explicit FrameWriter(int w = 0, int h = 0) : width(w), height(h), writer([this] { saveFrames(); }) {}
    ~FrameWriter() { finish(); }
    bool sample(SDL_Renderer *renderer, const fs::path &path) {
        {
            std::lock_guard lock(mutex);
            if (!writeError.empty())
                throw std::runtime_error(writeError);
            if (pending.size() >= 24)
                return false;
        }
        Surface surface(SDL_RenderReadPixels(renderer, nullptr), SDL_DestroySurface);
        if (!surface)
            throw std::runtime_error(SDL_GetError());
        {
            std::lock_guard lock(mutex);
            pending.emplace_back(path, std::move(surface));
        }
        ready.notify_one();
        return true;
    }
    void finish() {
        {
            std::lock_guard lock(mutex);
            stopping = true;
        }
        ready.notify_one();
        if (writer.joinable())
            writer.join();
    }
    void check() const {
        if (!writeError.empty())
            throw std::runtime_error(writeError);
    }
};
// The offline recorder samples the same rendered surface and audio devices
// heard during play. Timestamps include real decoder and loading delays.
class CampaignRecording {
    inline static CampaignRecording *active = nullptr;
    fs::path folder;
    std::ofstream frames;
    double next = 0;
    int number = 0, streams = 0;
    std::string failure;
    FrameWriter writer{960, 540};
    static double now() { return SDL_GetTicksNS() / 1e9; }

  public:
    const double begun = now();
    explicit CampaignRecording(const fs::path &path) : folder(path) {
        if (!fs::create_directories(folder / "frames"))
            throw std::runtime_error("Recording needs a fresh directory");
        frames.open(folder / "frames.tsv");
        frames.exceptions(std::ios::badbit | std::ios::failbit);
        frames.precision(12);
        active = this;
    }
    ~CampaignRecording() {
        active = nullptr;
    }
    static bool enabled() { return active != nullptr; }
    static void frame(SDL_Renderer *renderer) {
        auto *r = active;
        const auto requested = now();
        if (!r || requested < r->next)
            return;
        if (!r->writer.sample(renderer, r->folder / "frames" / (std::to_string(r->number) + ".bmp")))
            return;
        const double presented = now();
        r->frames << r->number++ << '\t' << presented - r->begun << '\n';
        r->next = std::max(requested, r->next + 1. / 60.);
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
        const double duration = now() - begun;
        writer.finish();
        writer.check();
        if (!failure.empty())
            throw std::runtime_error(failure);
        frames.flush();
        std::ofstream(folder / "recording.json")
            << Json{{"seconds", duration}, {"start_monotonic_seconds", begun}, {"frames", number}, {"streams", streams},
                    {"capture_target_hz", 60}}.dump(2);
    }
};
} // namespace ca
