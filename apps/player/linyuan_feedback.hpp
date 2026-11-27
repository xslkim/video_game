#pragma once
#include "changan_game.hpp"
#include "linyuan_sword.hpp"
#include "ui.hpp"
#include <algorithm>
#include <cmath>
#include <string_view>

namespace ca {
enum class LinyuanImpact { claw, collision, blast };
inline void linyuanStroke(Ink &ink, float x0, float y0, float x1, float y1, float width, SDL_Color rgba) {
    const float dx = x1 - x0, dy = y1 - y0, length = std::hypot(dx, dy);
    if (length < .1f)
        return;
    const float nx = -.5f * width * dy / length, ny = .5f * width * dx / length;
    const SDL_FColor color{rgba.r / 255.f, rgba.g / 255.f, rgba.b / 255.f, rgba.a / 255.f};
    const SDL_Vertex strip[] = {{{x0 + nx, y0 + ny}, color, {}},
                                {{x0 - nx, y0 - ny}, color, {}},
                                {{x1 - nx, y1 - ny}, color, {}},
                                {{x1 + nx, y1 + ny}, color, {}}};
    static constexpr int indices[] = {0, 1, 2, 0, 2, 3};
    SDL_RenderGeometry(ink.r, nullptr, strip, 4, indices, 6);
}

inline void linyuanOutlinedStroke(Ink &ink, float x0, float y0, float x1, float y1, float width,
                                  SDL_Color color) {
    linyuanStroke(ink, x0, y0, x1, y1, width + 2.f, {12, 30, 33, color.a});
    linyuanStroke(ink, x0, y0, x1, y1, width, color);
}

// A tapered closed shape keeps both the flight direction and impact readable on bright footage.
inline void linyuanShard(Ink &ink, Point p, float dx, float dy, float width, SDL_Color color) {
    const float length = std::max(1.f, std::hypot(dx, dy));
    const float x = float(p.x), y = float(p.y), nx = -dy * width / length, ny = dx * width / length;
    const SDL_FColor c{color.r / 255.f, color.g / 255.f, color.b / 255.f, color.a / 255.f};
    const SDL_Vertex diamond[] = {{{x, y}, c, {}},
                                  {{x + dx * .28f + nx, y + dy * .28f + ny}, c, {}},
                                  {{x + dx, y + dy}, c, {}},
                                  {{x + dx * .28f - nx, y + dy * .28f - ny}, c, {}}};
    static constexpr int indices[] = {0, 1, 2, 0, 2, 3};
    SDL_RenderGeometry(ink.r, nullptr, diamond, 4, indices, 6);
}

inline void impactSlash(Ink &ink, Point p, double age, bool amber, bool reduced, int slot, int tier) {
    if (age >= .24)
        return;
    const double k = (tier >= 3 ? 1.4 : 1.08) * (.78 + std::min(1., age / .09) * .22);
    const double side = slot % 2 ? -1. : 1.;
    const float a = float(std::min(1., (.24 - age) / .16));
    auto drawCut = [&](double s, double reachScale) {
        const double ks = k * reachScale;
        const SwordArc cut{{p.x - 54 * s * ks, p.y + 44 * ks},
                           {p.x + 8 * s * ks, p.y - 10 * ks},
                           {p.x + 48 * s * ks, p.y - 54 * ks}};
        swordRibbon(ink, cut, 0, 1, 10, {.03f, .16f, .17f, .92f * a}, SDL_BLENDMODE_BLEND);
        swordRibbon(ink, cut, 0, 1, reduced ? 9.f : 15.f,
                    amber ? SDL_FColor{1.f, .64f, .14f, .92f * a} : SDL_FColor{.24f, 1.f, .88f, .92f * a},
                    SDL_BLENDMODE_ADD);
        swordRibbon(ink, cut, .10, .96, 4.5f, {1.f, .99f, .90f, .98f * a}, SDL_BLENDMODE_BLEND);
    };
    drawCut(side, 1.0);
    if (amber || tier >= 3)
        drawCut(-side, .84);
}

inline void scatterArmor(Ink &ink, Point p, double age, std::string_view material, bool weak, int slot,
                         bool reduced) {
    const bool feather = material == "feather", vine = material == "vine", glass = material == "crystal";
    const float alpha = float(std::clamp((.45 - age) / .22, 0., 1.));
    const int count = feather ? 8 : vine ? 8 : 8 + slot % 5;
    SDL_Vertex triangles[12 * 6];
    for (int i = 0; i < count; ++i) {
        const double angle = i * 2.39996323 + slot * .41;
        const double speed = 94 + (i * 41 + slot * 11) % 143;
        const double dx = std::cos(angle), dy = std::sin(angle);
        const Point c{p.x + dx * (5 + speed * age) + (feather ? 12 * std::sin(8 * age + i) * age : 0),
                      p.y + dy * (5 + speed * .63 * age) - 72 * age + (feather ? 155 : 335) * age * age};
        const double turn = angle + age * ((i % 2 ? -1 : 1) * (feather ? 4.5 : 7.5) + i * .22);
        const double x = std::cos(turn), y = std::sin(turn);
        const double w = (vine ? 1.7 : feather ? 3.6 : 5.4) * (1 + .13 * (i % 3));
        const double l = (vine ? 12. : feather ? 17. : 8.) * (1 + .1 * (i % 4));
        auto vert = [&](double along, double across, SDL_FColor color) {
            return SDL_Vertex{
                {float(c.x + x * along - y * across), float(c.y + y * along + x * across)}, color, {}};
        };
        const SDL_FColor face = vine      ? SDL_FColor{.65f, .52f, .32f, alpha}
                                : glass   ? SDL_FColor{.66f, .96f, 1.f, alpha}
                                : feather ? SDL_FColor{.91f, .97f, 1.f, alpha}
                                          : SDL_FColor{.99f, .90f, .71f, alpha};
        const SDL_FColor under = vine               ? SDL_FColor{.28f, .24f, .15f, alpha}
                                 : feather || glass ? SDL_FColor{.22f, .42f, .50f, alpha}
                                                    : SDL_FColor{.40f, .34f, .26f, alpha};
        auto *v = triangles + 6 * i;
        v[0] = vert(l, 0, face);
        v[1] = vert(-l * .85, w, face);
        v[2] = vert(-l * .5, 0, face);
        v[3] = vert(l, 0, under);
        v[4] = vert(-l * .5, 0, under);
        v[5] = vert(-l * .56, -w * .72, under);
    }
    SDL_RenderGeometry(ink.r, nullptr, triangles, 6 * count, nullptr, 0);
    if (!weak)
        return;
    for (int i = 0; i < 4; ++i) {
        const double radius = 10 + age * (38 + 5 * i);
        const Point smoke{p.x + (i - 1.5) * (5 + 35 * age), p.y - 4 - 48 * age - i * 2};
        softGlow(ink, smoke, radius, radius * .84, {.24f, .18f, .12f, .52f * alpha}, SDL_BLENDMODE_BLEND);
    }
    for (int i = 0; i < 14; ++i) {
        const double a = i * 2.39996323 + .85, travel = 9 + (105 + (i * 51) % 144) * age;
        const float vx = float(std::cos(a)), vy = float(std::sin(a));
        const Point tip{p.x + vx * travel, p.y + vy * travel + age * age * 160};
        linyuanShard(ink, tip, -vx * (10 + i % 7), -vy * (10 + i % 7), 1.9f,
                     {255, 164, 28, Uint8(alpha * 255)});
    }
    softGlow(ink, p, 19, 16, {1.f, .58f, .09f, float((reduced ? .38 : .72) * std::max(0., 1. - age / .15))},
             SDL_BLENDMODE_ADD);
}

inline void linyuanDamageEdge(Ink &ink, float depth, float opacity) {
    const SDL_FColor outer{.72f, .065f, .045f, opacity}, inner{.32f, .025f, .025f, 0};
    const SDL_Vertex rim[] = {{{0, 0}, outer, {}},
                              {{1280, 0}, outer, {}},
                              {{1280, 720}, outer, {}},
                              {{0, 720}, outer, {}},
                              {{depth, depth * .70f}, inner, {}},
                              {{1280 - depth, depth * .70f}, inner, {}},
                              {{1280 - depth, 720 - depth * .70f}, inner, {}},
                              {{depth, 720 - depth * .70f}, inner, {}}};
    static constexpr int indices[] = {0, 1, 5, 0, 5, 4, 1, 2, 6, 1, 6, 5, 2, 3, 7, 2, 7, 6, 3, 0, 4, 3, 4, 7};
    SDL_RenderGeometry(ink.r, nullptr, rim, 8, indices, 24);
}
inline SDL_FRect linyuanBounds(const std::vector<Span> &spans, SDL_FRect picture) {
    if (spans.empty())
        return {};
    int left = spans.front().x0, right = spans.front().x1;
    for (const auto &span : spans) {
        left = std::min(left, int(span.x0));
        right = std::max(right, int(span.x1));
    }
    return {picture.x + left * picture.w / 640, picture.y + spans.front().y * picture.h / 360,
            (right - left) * picture.w / 640, (spans.back().y + 1 - spans.front().y) * picture.h / 360};
}
inline void linyuanBrackets(Ink &ink, SDL_FRect rect, float margin, SDL_Color color) {
    const float arm = std::clamp(std::min(rect.w, rect.h) / 4, 5.f, 15.f);
    for (int side : {-1, 1})
        for (int top : {-1, 1}) {
            const float x = side < 0 ? rect.x - margin : rect.x + rect.w + margin;
            const float y = top < 0 ? rect.y - margin : rect.y + rect.h + margin;
            ink.line(x, y, x - side * arm, y, color);
            ink.line(x, y, x, y - top * arm, color);
        }
}
inline void linyuanOutlinedBrackets(Ink &ink, SDL_FRect rect, float margin, SDL_Color color) {
    const float arm = std::clamp(std::min(rect.w, rect.h) / 4.f, 8.f, 20.f);
    for (int side : {-1, 1})
        for (int top : {-1, 1}) {
            const float x = side < 0 ? rect.x - margin : rect.x + rect.w + margin;
            const float y = top < 0 ? rect.y - margin : rect.y + rect.h + margin;
            linyuanOutlinedStroke(ink, x, y, x - side * arm, y, 2.6f, color);
            linyuanOutlinedStroke(ink, x, y, x, y - top * arm, 2.6f, color);
        }
}
inline void linyuanStrokeRing(Ink &ink, Point center, float radius, float width, SDL_Color color,
                             int segments = 28) {
    for (int i = 0; i < segments; ++i) {
        const double a = 6.283185307 * i / segments;
        const double b = 6.283185307 * (i + 1) / segments;
        linyuanStroke(ink, float(center.x + radius * std::cos(a)), float(center.y + radius * std::sin(a)),
                      float(center.x + radius * std::cos(b)), float(center.y + radius * std::sin(b)), width,
                      color);
    }
}
inline void drawLinyuanTargetLock(Ink &ink, Point center, float radius, double timeSec, double openAge,
                                  double urgency, bool isProjectile = false) {
    const float snap = float(1. + .52 * std::clamp(1. - openAge / .22, 0., 1.));
    const float pulse = float(2.5 * std::sin(timeSec * 11.));
    const float r = std::clamp(radius, 18.f, 44.f) * snap + pulse;
    const bool hot = urgency > 0. || isProjectile;
    softGlow(ink, center, r * 1.75, r * 1.55,
             hot ? SDL_FColor{1.f, .42f, .14f, .34f} : SDL_FColor{1.f, .76f, .18f, .30f},
             SDL_BLENDMODE_ADD);
    linyuanStrokeRing(ink, center, r, 5.8f, {8, 16, 20, 220});
    linyuanStrokeRing(ink, center, r, 2.8f,
                      hot ? SDL_Color{255, 114, 60, 250} : SDL_Color{255, 214, 74, 250});
    linyuanStrokeRing(ink, center, r + 6.5f, 1.8f, {92, 255, 218, 210});
    const float tipOff = r + 9.f - float(2.2 * (0.5 + 0.5 * std::sin(timeSec * 12.)));
    for (int k = 0; k < 4; ++k) {
        const double ang = .78539816 + k * 1.5707963;
        const float cx = float(center.x + tipOff * std::cos(ang));
        const float cy = float(center.y + tipOff * std::sin(ang));
        const float ix = float(center.x + (tipOff - 8.f) * std::cos(ang));
        const float iy = float(center.y + (tipOff - 8.f) * std::sin(ang));
        linyuanOutlinedStroke(ink, cx, cy, ix, iy, 3.0f, {255, 224, 110, 255});
    }
}
inline void linyuanCountdown(Ink &ink, Point center, float radius, double remaining) {
    const SDL_Color orange{255, 102, 58, 240};
    const int pieces = std::clamp(int(std::ceil(32 * remaining)), 1, 32);
    for (int i = 0; i < pieces; ++i) {
        const double a = i * .19635 - 1.5708, b = a + .19635;
        linyuanOutlinedStroke(ink, float(center.x + radius * std::cos(a)), float(center.y + radius * std::sin(a)),
                              float(center.x + radius * std::cos(b)), float(center.y + radius * std::sin(b)),
                              3.2f, orange);
    }
}
// Effects use elapsed seconds so animation remains continuous at different refresh rates.
inline void drawLinyuanEffect(Ink &ink, Cue cue, Point point, double age, bool reducedFlash = false,
                              int tier = 2, bool weak = false, LinyuanImpact attack = LinyuanImpact::claw,
                              int scoreDelta = 0, std::string_view material = {}, int lives = -1,
                              int swordSlot = 0, bool returned = false, double returnSeconds = .24) {
    const double remaining = std::clamp(1. - age / .45, 0., 1.);
    const auto alpha = Uint8(255 * remaining * remaining);
    const SDL_Color cyan{77, 255, 210, alpha}, amber{255, 201, 74, alpha};
    const SDL_Color ice{207, 227, 255, alpha}, orange{255, 74, 46, alpha};
    if (cue == Cue::empty) {
        ink.text(640, 120, 25, "剑匣已空  ·  右键或 R 收剑", ice, true);
        return;
    }
    if (cue == Cue::civilian) {
        softGlow(ink, point, 55, 48, {.61f, .76f, 1.f, float((reducedFlash ? .32 : .73) * remaining)},
                 SDL_BLENDMODE_ADD);
        ink.ring(point, 24, ice);
        linyuanOutlinedStroke(ink, float(point.x - 15), float(point.y + 15), float(point.x + 15),
                              float(point.y - 15), 4, ice);
        swordFlight(ink, point, swordSlot, age, reducedFlash);
        ink.box(525, 125, 230, 47, {24, 37, 52, alpha});
        ink.text(640, 132, 25, "误伤  ·  保护云姨", ice, true);
        return;
    }
    if (cue == Cue::hurt) {
        const float hold = float(std::clamp((.78 - age) / .40, 0., 1.));
        const SDL_Color redInk{255, 136, 104, Uint8(255 * hold)};
        linyuanDamageEdge(ink, 104 + 72 * hold, (reducedFlash ? .46f : .86f) * hold);
        ink.box(520, 125, 240, 49, {41, 18, 22, Uint8(230 * hold)});
        ink.box(520, 125, 4, 49, redInk);
        ink.text(640, 132, 27, lives >= 0 ? "受击  −1    剩 " + std::to_string(lives) + " 命" : "受击  −1",
                 redInk, true);
        if (age >= .34)
            return;
        if (attack == LinyuanImpact::claw) {
            for (int i = 0; i < 3; ++i) {
                const Point root{358. + 100 * i, 194. + 17 * i};
                linyuanShard(ink, root, 172, 250, 8, {71, 20, 23, alpha});
                linyuanShard(ink, root, 172, 250, 4, {255, 142, 102, alpha});
            }
        } else if (attack == LinyuanImpact::blast) {
            for (int i = 0; i < 12; ++i) {
                const double a = i * .523599;
                linyuanShard(ink, {640 + 620 * std::cos(a), 360 + 350 * std::sin(a)}, float(-240 * std::cos(a)),
                             float(-160 * std::sin(a)), 7, orange);
            }
        } else {
            for (int i = 0; i < 5; ++i) {
                const float x = 140.f + i * 218.f;
                linyuanOutlinedStroke(ink, x, 0, x + 50, 65, 7, orange);
                linyuanOutlinedStroke(ink, x + 50, 65, x + 26, 115, 4, orange);
                linyuanShard(ink, {x + 50, 65}, 60, 26, 3, orange);
            }
        }
        return;
    }
    if (cue == Cue::reload || cue == Cue::ready || cue == Cue::none)
        return;
    if (cue == Cue::special) {
        const double slowFade = std::clamp(1. - age / .65, 0., 1.);
        const auto sAlpha = Uint8(255 * slowFade);
        if (!reducedFlash && age < .05) {
            SDL_SetRenderDrawColor(ink.r, 232, 255, 250, Uint8(120 * (1. - age / .05)));
            SDL_FRect full{0, 0, 1280, 720};
            SDL_RenderFillRect(ink.r, &full);
        }
        softGlow(ink, point, 40 + 180 * std::min(1., age / .28), 34 + 150 * std::min(1., age / .28),
                 {.22f, 1.f, .88f, float((reducedFlash ? .35 : .80) * slowFade)}, SDL_BLENDMODE_ADD);
        ink.ring(point, int(18 + 220 * std::min(1., age / .30)), {77, 255, 210, sAlpha});
        ink.ring(point, int(10 + 160 * std::min(1., age / .24)), {255, 214, 96, sAlpha});
        for (int i = 0; i < 8; ++i) {
            const double angle = i * .78539816 + .25;
            const Point edge{640. + 780. * std::cos(angle), 360. + 460. * std::sin(angle)};
            const SwordArc arc = swordArc(edge, point, i, false);
            const double travel = std::clamp((age - i * .018) / .14, 0., 1.);
            if (travel > 0 && age < .34) {
                const double head = travel, tail = std::max(0., head - .55);
                swordRibbon(ink, arc, tail, head, reducedFlash ? 8.f : 15.f,
                            {.22f, 1.f, .86f, float(.9f * slowFade)}, SDL_BLENDMODE_ADD);
                if (travel < 1.)
                    flyingSword(ink, arc.at(head), arc.tangent(head), 1.15, float(slowFade));
            }
        }
        scatterArmor(ink, point, age, material.empty() ? "ceramic" : material, true, 0, reducedFlash);
        impactSlash(ink, point, age, true, reducedFlash, 0, 3);
        const float ty = std::clamp(float(point.y) - 82.f - float(28 * age), 96.f, 620.f);
        ink.box(float(point.x) - 86.f, ty - 2, 172, 34, {14, 34, 36, Uint8(.86f * sAlpha)});
        ink.text(float(point.x), ty, 24, "万剑归宗", {255, 214, 96, sAlpha}, true);
        return;
    }
    const auto color = cue == Cue::intercept || weak || tier == 3 ? amber : cyan;
    swordFlight(ink, point, swordSlot, age, reducedFlash);
    if (cue == Cue::miss) {
        if (material == "water") {
            ink.ring(point, int(5 + age * 76), {130, 201, 210, alpha});
            ink.ring(point, int(3 + age * 47), {185, 227, 227, alpha});
        } else if (material == "stone" || material == "metal") {
            for (int i = 0; i < 7; ++i) {
                const double a = i * .9, d = 5 + age * 110;
                ink.line(float(point.x + d * std::cos(a)), float(point.y + d * std::sin(a)),
                         float(point.x + (d + 5) * std::cos(a)), float(point.y + (d + 5) * std::sin(a)), amber);
            }
        } else if (material == "earth" || material == "bamboo") {
            const SDL_Color tint =
                material == "earth" ? SDL_Color{163, 132, 95, alpha} : SDL_Color{143, 178, 83, alpha};
            for (int i = 0; i < 8; ++i)
                ink.box(float(point.x + (i - 3.5) * age * 28),
                        float(point.y + age * age * 210 - (i % 3) * age * 85), material == "earth" ? 3.f : 7.f,
                        3.f, tint);
        } else
            ink.ring(point, int(5 + age * 32), {155, 165, 161, alpha});
        return;
    }
    const float x = float(point.x), y = float(point.y);
    if (age < .22) {
        const float ringR = 14.f + float(88. * std::min(1., age / .20));
        const Uint8 ra = Uint8(240 * std::max(0., 1. - age / .22));
        linyuanStrokeRing(ink, point, ringR, 4.8f, {10, 18, 22, Uint8(.82f * ra)}, 22);
        linyuanStrokeRing(ink, point, ringR, 2.4f, {color.r, color.g, color.b, ra}, 22);
    }
    if (age < .16)
        softGlow(ink, point, 44, 38,
                 (weak || cue == Cue::intercept || tier >= 3)
                     ? SDL_FColor{1.f, .68f, .18f, float((reducedFlash ? .36 : .72) * (1. - age / .16))}
                     : SDL_FColor{.26f, 1.f, .88f, float((reducedFlash ? .32 : .64) * (1. - age / .16))},
                 SDL_BLENDMODE_ADD);
    scatterArmor(ink, point, age, material, weak, swordSlot, reducedFlash);
    impactSlash(ink, point, age, weak || cue == Cue::intercept, reducedFlash, swordSlot, tier);
    if (returned && age >= .10) {
        returnSword(ink, point, swordSlot, (age - .10) / returnSeconds, reducedFlash);
        caseGlint(ink, caseMouth(swordSlot), age - .10 - returnSeconds, reducedFlash);
    }
    if (scoreDelta > 0 || cue == Cue::hit || cue == Cue::intercept || cue == Cue::purify) {
        const char *label = cue == Cue::intercept ? "拦截"
                            : returned            ? "弱点回剑"
                            : cue == Cue::hit     ? "破甲"
                            : tier == 3           ? "精英击破"
                            : weak                ? "弱点击破"
                                                  : "击破";
        const std::string text =
            scoreDelta > 0 ? std::string(label) + "  +" + std::to_string(scoreDelta) : label;
        const float tx = std::clamp(x, 108.f, 1172.f);
        const float ty = std::clamp((y < 190.f ? y + 66.f : y - 72.f) - float(25 * age), 99.f, 624.f);
        const Uint8 opacity = Uint8(255 * std::clamp((.45 - age) / .15, 0., 1.));
        const float halfWidth = 36.f + (weak || tier == 3 ? 26.f : 0.f) +
                                (scoreDelta > 0 ? 15.f + 7.f * std::to_string(scoreDelta).size() : 0.f);
        ink.box(tx - halfWidth, ty - 2, 2 * halfWidth, 34, {14, 28, 30, Uint8(.88f * opacity)});
        ink.box(tx - halfWidth, ty - 2, 3, 34, {color.r, color.g, color.b, opacity});
        ink.text(tx, ty, 25, text, {color.r, color.g, color.b, opacity}, true);
    }
}

inline void drawLinyuanReticle(Ink &ink, Point point, int arrows, bool reloading, bool target, bool weak,
                               bool protect, bool specialReady = false) {
    SDL_Color color = protect  ? SDL_Color{225, 118, 106, 255}
                      : weak   ? SDL_Color{255, 214, 74, 255}
                      : target ? SDL_Color{77, 255, 210, 255}
                               : SDL_Color{242, 245, 247, 255};
    if (arrows == 0 || reloading)
        color = {140, 147, 155, 255};
    const float x = float(point.x), y = float(point.y);
    if (specialReady)
        linyuanStrokeRing(ink, point, 26.f, 2.2f, {255, 210, 86, 225}, 24);
    if (weak && !protect) {
        linyuanStrokeRing(ink, point, 22.f, 4.5f, {10, 18, 22, 210}, 24);
        linyuanStrokeRing(ink, point, 22.f, 2.4f, {255, 214, 74, 245}, 24);
        linyuanStrokeRing(ink, point, 11.5f, 1.8f, {255, 246, 175, 235}, 20);
        linyuanOutlinedStroke(ink, x, y - 27, x, y - 15, 2.8f, color);
        linyuanOutlinedStroke(ink, x, y + 27, x, y + 15, 2.8f, color);
        linyuanOutlinedStroke(ink, x - 27, y, x - 15, y, 2.8f, color);
        linyuanOutlinedStroke(ink, x + 27, y, x + 15, y, 2.8f, color);
    } else if (target && !protect) {
        linyuanStrokeRing(ink, point, 19.f, 4.0f, {10, 18, 22, 195}, 22);
        linyuanStrokeRing(ink, point, 19.f, 2.0f, {77, 255, 210, 235}, 22);
    } else if (protect) {
        linyuanStrokeRing(ink, point, 20.f, 4.5f, {12, 16, 20, 215}, 22);
        linyuanStrokeRing(ink, point, 20.f, 2.4f, {235, 112, 102, 245}, 22);
        linyuanOutlinedStroke(ink, x - 12, y - 12, x + 12, y + 12, 3.2f, {235, 112, 102, 255});
        linyuanOutlinedStroke(ink, x - 12, y + 12, x + 12, y - 12, 3.2f, {235, 112, 102, 255});
    }
    for (int sign : {-1, 1}) {
        linyuanOutlinedStroke(ink, x + sign * 10, y - 17, x + sign * 17, y - 10, 2.8f, color);
        linyuanOutlinedStroke(ink, x + sign * 10, y + 17, x + sign * 17, y + 10, 2.8f, color);
    }
    ink.box(x - 3, y - 3, 7, 7, {0, 0, 0, 255});
    ink.box(x - 2, y - 2, 5, 5, weak ? SDL_Color{255, 238, 128, 255} : color);
    for (int i = 0; i < 8; ++i)
        ink.box(x - 24 + i * 6, y + 28, 4, 5, i < arrows ? color : SDL_Color{60, 65, 63, 225});
}
} // namespace ca
