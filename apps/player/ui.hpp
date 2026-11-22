#pragma once
#include "game.hpp"
#include <SDL3/SDL.h>
namespace dc {
struct Ink {
    SDL_Renderer *r;
    std::map<std::pair<std::string, int>, SDL_Texture *> cache;
    explicit Ink(SDL_Renderer *renderer) : r(renderer) {}
    ~Ink();
    void box(float x, float y, float w, float h, SDL_Color c);
    void line(float x, float y, float xx, float yy, SDL_Color c);
    void text(float x, float y, int size, const std::string &s, SDL_Color color, bool center = false);
    void ring(Point p, int radius, SDL_Color c);
    void star(Point p, int radius, SDL_Color c);
};
inline constexpr SDL_Color ivory{253, 241, 211, 255}, gold{245, 194, 101, 255}, red{247, 111, 90, 255},
    dark{29, 24, 19, 222};
struct Layout {
    SDL_FRect video;
    SDL_FRect picture;
    explicit Layout(bool tv, double shake = 0)
        : video(tv ? SDL_FRect{85.3333f, 48, 1109.3334f, 624} : SDL_FRect{0, 0, 1280, 720}),
          picture{video.x - video.w * .01f + float(shake), video.y - video.h * .01f, video.w * 1.02f,
                  video.h * 1.02f} {}
    Point fromVideo(Point p) const {
        return {picture.x + p.x * picture.w / 1280, picture.y + p.y * picture.h / 720};
    }
    Point toVideo(Point p) const {
        if (p.x < video.x || p.x >= video.x + video.w || p.y < video.y || p.y >= video.y + video.h)
            return {-1, -1};
        return {(p.x - picture.x) * 1280 / picture.w, (p.y - picture.y) * 720 / picture.h};
    }
};
void drawUI(Ink &ink, const Game &g, Layout layout, Point cursor, bool tv, bool locked, bool subtitles,
            const std::string &notice);
} // namespace dc
