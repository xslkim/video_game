#pragma once
#include "ui.hpp"
#include <SDL3/SDL.h>
#include <algorithm>
#include <cmath>
#include <memory>

namespace ca {
struct GamepadController {
    std::unique_ptr<SDL_Gamepad, decltype(&SDL_CloseGamepad)> pad{nullptr, SDL_CloseGamepad};
    bool triggerDown = false;
    uint64_t lastTick = 0;

    void ensureOpen() {
        if (pad && SDL_GamepadConnected(pad.get()))
            return;
        pad.reset();
        int count = 0;
        std::unique_ptr<SDL_JoystickID[], decltype(&SDL_free)> ids(SDL_GetGamepads(&count), SDL_free);
        if (ids && count > 0)
            pad.reset(SDL_OpenGamepad(ids[0]));
    }

    template <typename FireFn, typename ReloadFn, typename SpecialFn, typename StartFn>
    void poll(SDL_Event &e, dc::Point &cursor, FireFn &&onFire, ReloadFn &&onReload, SpecialFn &&onSpecial,
              StartFn &&onStart) {
        if (e.type == SDL_EVENT_GAMEPAD_ADDED)
            ensureOpen();
        if (e.type == SDL_EVENT_GAMEPAD_REMOVED)
            pad.reset();
        if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN) {
            if (cursor.x < 0)
                cursor = {640, 360};
            const auto b = e.gbutton.button;
            if (b == SDL_GAMEPAD_BUTTON_SOUTH || b == SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER)
                onFire(cursor, e.gbutton.timestamp);
            else if (b == SDL_GAMEPAD_BUTTON_WEST)
                onReload();
            else if (b == SDL_GAMEPAD_BUTTON_NORTH)
                onSpecial();
            else if (b == SDL_GAMEPAD_BUTTON_START)
                onStart();
        }
    }

    template <typename FireFn>
    void updateAim(dc::Point &cursor, int width, int height, FireFn &&onFire) {
        ensureOpen();
        const uint64_t now = SDL_GetTicksNS();
        const double dt = lastTick ? std::clamp((now - lastTick) / 1e9, 0., .05) : 0.;
        lastTick = now;
        if (!pad)
            return;
        auto norm = [](Sint16 v) {
            const double f = v / 32767.;
            return std::abs(f) > .15 ? f : 0.;
        };
        const double sx = norm(SDL_GetGamepadAxis(pad.get(), SDL_GAMEPAD_AXIS_LEFTX));
        const double sy = norm(SDL_GetGamepadAxis(pad.get(), SDL_GAMEPAD_AXIS_LEFTY));
        if ((sx != 0 || sy != 0) && dt > 0) {
            if (cursor.x < 0)
                cursor = {width * .5, height * .5};
            cursor.x = std::clamp(cursor.x + sx * 760. * dt, 0., double(width - 1));
            cursor.y = std::clamp(cursor.y + sy * 760. * dt, 0., double(height - 1));
        }
        const bool rt = SDL_GetGamepadAxis(pad.get(), SDL_GAMEPAD_AXIS_RIGHT_TRIGGER) > 16000;
        if (rt && !triggerDown) {
            if (cursor.x < 0)
                cursor = {width * .5, height * .5};
            onFire(cursor, now);
        }
        triggerDown = rt;
    }
};
} // namespace ca
