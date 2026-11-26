#pragma once
#include "ui.hpp"
#include <algorithm>
#include <array>
#include <cmath>

namespace ca {
using dc::Ink;
using dc::Point;

struct SwordArc {
    Point from, bend, to;
    Point at(double u) const {
        const double v = 1 - u;
        return {v * v * from.x + 2 * v * u * bend.x + u * u * to.x,
                v * v * from.y + 2 * v * u * bend.y + u * u * to.y};
    }
    Point tangent(double u) const {
        const double x = (1 - u) * (bend.x - from.x) + u * (to.x - bend.x);
        const double y = (1 - u) * (bend.y - from.y) + u * (to.y - bend.y);
        const double norm = std::max(1., std::hypot(x, y));
        return {x / norm, y / norm};
    }
};

inline SwordArc swordArc(Point start, Point end, int slot, bool recalling) {
    const double direction = slot % 2 ? -1. : 1.;
    const double dx = end.x - start.x, dy = end.y - start.y;
    const double distance = std::max(1., std::hypot(dx, dy));
    const double bow = std::clamp(distance * (recalling ? .35 : .28), 28., 226.) * (1. + (slot / 2) * .07);
    Point bend{(start.x + end.x) * .5 - direction * dy / distance * bow,
               (start.y + end.y) * .5 + direction * dx / distance * bow};
    return {start, bend, end};
}

// Vertex alpha tapers both across and along this curved ribbon. Changing the
// renderer draw blend mode applies to untextured SDL geometry on every backend.
inline void swordRibbon(Ink &ink, const SwordArc &arc, double begin, double end, float width, SDL_FColor tint,
                        SDL_BlendMode blend) {
    if (end - begin < .001 || tint.a <= 0)
        return;
    constexpr int segments = 18;
    SDL_Vertex ribbon[(segments + 1) * 3];
    int indices[segments * 12];
    for (int i = 0; i <= segments; ++i) {
        const double along = double(i) / segments, u = begin + (end - begin) * along;
        const Point p = arc.at(u), dir = arc.tangent(u);
        const float spread = width * float(std::sin(along * 3.14159265) * .64 + along * .31 + .05);
        for (int side = -1; side <= 1; ++side) {
            auto c = tint;
            c.a *= side == 0 ? float(along * (2 - along)) : 0.f;
            ribbon[3 * i + side + 1] = {
                {float(p.x - side * dir.y * spread), float(p.y + side * dir.x * spread)}, c, {}};
        }
        if (i < segments) {
            for (int band = 0; band < 2; ++band) {
                int a = 3 * i + band;
                const int quad[] = {a, a + 1, a + 3, a + 1, a + 4, a + 3};
                std::copy_n(quad, 6, indices + 12 * i + 6 * band);
            }
        }
    }
    SDL_SetRenderDrawBlendMode(ink.r, blend);
    SDL_RenderGeometry(ink.r, nullptr, ribbon, (segments + 1) * 3, indices, segments * 12);
    SDL_SetRenderDrawBlendMode(ink.r, SDL_BLENDMODE_BLEND);
}

inline void softGlow(Ink &ink, Point center, double rx, double ry, SDL_FColor tint, SDL_BlendMode mode) {
    constexpr int sides = 20;
    SDL_Vertex verts[sides + 1];
    int indices[sides * 3];
    verts[0] = {{float(center.x), float(center.y)}, tint, {}};
    tint.a = 0;
    for (int i = 0; i < sides; ++i) {
        const double angle = 6.28318531 * i / sides;
        verts[i + 1] = {
            {float(center.x + rx * std::cos(angle)), float(center.y + ry * std::sin(angle))}, tint, {}};
        indices[i * 3] = 0;
        indices[i * 3 + 1] = i + 1;
        indices[i * 3 + 2] = (i + 1) % sides + 1;
    }
    SDL_SetRenderDrawBlendMode(ink.r, mode);
    SDL_RenderGeometry(ink.r, nullptr, verts, sides + 1, indices, sides * 3);
    SDL_SetRenderDrawBlendMode(ink.r, SDL_BLENDMODE_BLEND);
}

// Five pieces of one double-edged sword: two blade bevels, guard, grip, pommel.
inline void flyingSword(Ink &ink, Point tip, Point direction, double scale, float opacity) {
    constexpr SDL_FPoint profile[] = {{0, 0},      {-16, -5},  {-51, -4},    {-55, 0},     {-51, 4},
                                      {-16, 5},    {-49, -13}, {-55, -15},   {-59, -5},    {-59, 5},
                                      {-55, 15},   {-49, 13},  {-58, -2.3f}, {-72, -2.3f}, {-72, 2.3f},
                                      {-58, 2.3f}, {-76, 0}};
    SDL_Vertex verts[std::size(profile)];
    for (size_t i = 0; i < std::size(profile); ++i) {
        const auto p = profile[i];
        SDL_FColor c = i == 0 || i == 3     ? SDL_FColor{.98f, 1.f, .95f, opacity}
                       : i == 1 || i == 2   ? SDL_FColor{.27f, .74f, .77f, opacity}
                       : i == 4 || i == 5   ? SDL_FColor{.78f, .98f, .97f, opacity}
                       : i >= 12 && i <= 15 ? SDL_FColor{.07f, .20f, .22f, opacity}
                                            : SDL_FColor{.67f, .93f, .79f, opacity};
        verts[i] = {{float(tip.x + scale * (direction.x * p.x - direction.y * p.y)),
                     float(tip.y + scale * (direction.y * p.x + direction.x * p.y))},
                    c,
                    {}};
    }
    constexpr int faces[] = {0, 1, 3, 1, 2, 3,  0, 3,  5,  3,  4,  5,  6,  7,  8,  6,  8,  3,
                             3, 8, 9, 3, 9, 11, 9, 10, 11, 12, 13, 14, 12, 14, 15, 13, 16, 14};
    SDL_RenderGeometry(ink.r, nullptr, verts, int(std::size(verts)), faces, int(std::size(faces)));
}

inline Point caseMouth(int slot) {
    constexpr double lanes[] = {-94., 51., -48., 94., -72., 73., -24., 26.};
    return {1105. + lanes[slot % 8], 682. + (slot % 3) * 9.};
}

inline void swordFlight(Ink &ink, Point impact, int slot, double age, bool reduced) {
    if (age < 0 || age >= .16)
        return;
    const Point mouth = caseMouth(slot);
    const SwordArc arc = swordArc(mouth, impact, slot, false);
    const double travel = std::min(1., age / .064);
    const double head = .26 + .74 * (1 - (1 - travel) * (1 - travel));
    const double tail = std::max(0., head - .57) + .56 * std::clamp((age - .064) / .096, 0., 1.);
    const float alpha = float(std::min(1., (.16 - age) / .096));
    swordRibbon(ink, arc, tail, head, 10.f, {.02f, .23f, .23f, .93f * alpha}, SDL_BLENDMODE_BLEND);
    swordRibbon(ink, arc, tail, head, reduced ? 9.f : 18.f, {.14f, .91f, .78f, (reduced ? .41f : .88f) * alpha},
                SDL_BLENDMODE_ADD);
    if (age < .076)
        flyingSword(ink, arc.at(head), arc.tangent(head), 1.05, float(std::min(1., (.076 - age) / .012)));
}

inline void returnSword(Ink &ink, Point from, int slot, double progress, bool reduced) {
    if (progress < 0 || progress >= 1)
        return;
    const SwordArc arc = swordArc(from, caseMouth(slot), slot, true);
    const double head = progress * (1.55 - .55 * progress);
    const double tail = std::max(0., head - .31);
    const float alpha = float(std::min({1., progress * 18, (1 - progress) * 16}));
    swordRibbon(ink, arc, tail, head, 6, {.01f, .17f, .20f, .9f * alpha}, SDL_BLENDMODE_BLEND);
    swordRibbon(ink, arc, tail, head, reduced ? 6.f : 13.f, {.18f, 1.f, .84f, (reduced ? .46f : .92f) * alpha},
                SDL_BLENDMODE_ADD);
    flyingSword(ink, arc.at(head), arc.tangent(head), .66, alpha);
}

inline void caseGlint(Ink &ink, Point p, double age, bool reduced) {
    if (age < 0 || age > .19)
        return;
    const float intensity = float(1 - age / .19);
    softGlow(ink, p, 47, 19, {.18f, 1.f, .86f, (reduced ? .48f : .87f) * intensity}, SDL_BLENDMODE_ADD);
    SwordArc glint{{p.x - 55, p.y + 15}, p, {p.x + 55, p.y - 15}};
    swordRibbon(ink, glint, .02, 1, 4, {.68f, 1.f, .86f, intensity}, SDL_BLENDMODE_ADD);
}

// The visual warning is attached to the authored eye, claw or needle emitter on
// the currently displayed source frame, including frames after the hit mask closes.
inline void threatGlow(Ink &ink, Point p, double progress, bool reduced) {
    const double wave = .5 - .5 * std::cos(6.28318531 * (1.55 * progress + .35 * progress * progress));
    const float strength = float(reduced ? .51 + .22 * progress : .49 + .37 * wave + .13 * progress);
    const double size = (reduced ? 24 : 29) + 12 * wave;
    softGlow(ink, p, size, size * .76, {.53f, .018f, .007f, strength}, SDL_BLENDMODE_BLEND);
    softGlow(ink, p, size * .72, size * .50, {1.f, .12f, .035f, strength}, SDL_BLENDMODE_ADD);
    softGlow(ink, p, 8 + 5 * progress, 5 + 3 * progress, {1.f, .55f, .23f, strength}, SDL_BLENDMODE_ADD);
}
} // namespace ca
