#include "ui.hpp"
#include <windows.h>
#include <numbers>
namespace dc {
Ink::~Ink() {
    for (auto &[key, t] : cache)
        SDL_DestroyTexture(t);
}
void Ink::box(float x, float y, float w, float h, SDL_Color c) {
    SDL_SetRenderDrawColor(r, c.r, c.g, c.b, c.a);
    SDL_FRect rect{x, y, w, h};
    SDL_RenderFillRect(r, &rect);
}
void Ink::line(float x, float y, float xx, float yy, SDL_Color c) {
    SDL_SetRenderDrawColor(r, c.r, c.g, c.b, c.a);
    SDL_RenderLine(r, x, y, xx, yy);
}
void Ink::text(float x, float y, int size, const std::string &str, SDL_Color color, bool center) {
    if (str.empty())
        return;
    auto key = std::make_pair(str, size);
    if (!cache.contains(key)) {
        if (cache.size() > 450) {
            for (auto &[_, t] : cache)
                SDL_DestroyTexture(t);
            cache.clear();
        }
        int len = MultiByteToWideChar(CP_UTF8, 0, str.data(), int(str.size()), nullptr, 0);
        std::wstring wide(len, L' ');
        MultiByteToWideChar(CP_UTF8, 0, str.data(), int(str.size()), wide.data(), len);
        HDC dc = CreateCompatibleDC(nullptr);
        HFONT font =
            CreateFontW(-size, 0, 0, 0, size >= 48 ? FW_BOLD : FW_MEDIUM, 0, 0, 0, DEFAULT_CHARSET,
                        OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, ANTIALIASED_QUALITY, DEFAULT_PITCH,
                        size >= 46 ? L"Georgia" : L"Microsoft YaHei UI");
        auto oldFont = SelectObject(dc, font);
        SIZE extent{};
        GetTextExtentPoint32W(dc, wide.data(), len, &extent);
        BITMAPINFO bi{};
        bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        bi.bmiHeader.biWidth = extent.cx + 4;
        bi.bmiHeader.biHeight = -(extent.cy + 4);
        bi.bmiHeader.biPlanes = 1;
        bi.bmiHeader.biBitCount = 32;
        bi.bmiHeader.biCompression = BI_RGB;
        void *pixels = nullptr;
        HBITMAP bmp = CreateDIBSection(dc, &bi, DIB_RGB_COLORS, &pixels, nullptr, 0);
        if (!bmp || !pixels) {
            SelectObject(dc, oldFont);
            DeleteObject(font);
            DeleteDC(dc);
            return;
        }
        auto oldBmp = SelectObject(dc, bmp);
        int w = extent.cx + 4, h = extent.cy + 4;
        std::memset(pixels, 0, size_t(w) * h * 4);
        SetBkMode(dc, TRANSPARENT);
        SetTextColor(dc, RGB(255, 255, 255));
        TextOutW(dc, 1, 1, wide.data(), len);
        GdiFlush();
        auto *data = static_cast<uint32_t *>(pixels);
        for (int i = 0; i < w * h; ++i)
            data[i] = 0x00ffffffu | ((data[i] & 255) << 24);
        auto *tex = SDL_CreateTexture(r, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STATIC, w, h);
        if (tex) {
            SDL_UpdateTexture(tex, nullptr, pixels, w * 4);
            SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_BLEND);
        }
        SelectObject(dc, oldBmp);
        SelectObject(dc, oldFont);
        DeleteObject(bmp);
        DeleteObject(font);
        DeleteDC(dc);
        if (!tex)
            return;
        cache.emplace(key, tex);
    }
    auto *tex = cache.at(key);
    float w, h;
    SDL_GetTextureSize(tex, &w, &h);
    SDL_SetTextureColorMod(tex, color.r, color.g, color.b);
    SDL_SetTextureAlphaMod(tex, color.a);
    SDL_FRect dest{center ? x - w / 2 : x, y, w, h};
    SDL_RenderTexture(r, tex, nullptr, &dest);
}
void Ink::ring(Point p, int radius, SDL_Color c) {
    Point prev{p.x + radius, p.y};
    for (int i = 1; i <= 48; ++i) {
        double ang = i * std::numbers::pi / 24;
        Point now{p.x + radius * cos(ang), p.y + radius * sin(ang)};
        line(float(prev.x), float(prev.y), float(now.x), float(now.y), c);
        prev = now;
    }
}
void Ink::star(Point p, int radius, SDL_Color c) {
    SDL_Vertex v[30]{};
    for (int i = 0; i < 10; ++i) {
        auto pos = [&](int k) {
            double a = -std::numbers::pi / 2 + k * std::numbers::pi / 5;
            double r = k % 2 ? radius * .47 : radius;
            return SDL_FPoint{float(p.x + r * cos(a)), float(p.y + r * sin(a))};
        };
        v[i * 3].position = {float(p.x), float(p.y)};
        v[i * 3 + 1].position = pos(i);
        v[i * 3 + 2].position = pos(i + 1);
    }
    for (auto &a : v)
        a.color = {c.r / 255.f, c.g / 255.f, c.b / 255.f, c.a / 255.f};
    SDL_RenderGeometry(r, nullptr, v, 30, nullptr, 0);
}
static void button(Ink &k, int x, int y, int w, const std::string &s, bool primary) {
    k.box(x, y, w, 48, primary ? gold : dark);
    k.text(x + w / 2, y + 9, 22, s, primary ? SDL_Color{38, 30, 22, 255} : ivory, true);
}
static std::string chapter(const Game &g) {
    std::string id = g.clip->id.substr(0, 2);
    if (id == "A0")
        return "警长办公室";
    if (id == "A1")
        return "主街街口";
    if (id == "A2")
        return "旅馆与铁匠铺";
    if (id == "A3")
        return "杂货店";
    if (id == "A4")
        return "酒馆门廊";
    return "副警长星徽";
}
void drawUI(Ink &k, const Game &g, Layout l, Point cursor, bool tv, bool locked, bool subs,
            const std::string &notice) {
    if (g.screen != Screen::play || g.paused) {
        for (int x = 0; x < 920; x += 4)
            k.box(x, 0, 4, 720, {19, 15, 12, Uint8(235 * std::pow(1 - x / 925., .70))});
        k.box(70, 137, 52, 3, gold);
        k.text(70, 161, 24, "尘溪镇   /   西部光枪剧场", gold);
        if (g.screen == Screen::title) {
            k.text(65, 197, 80, "Dust Creek", ivory);
            k.text(70, 311, 28, "第一章    主街求援", ivory);
            k.text(70, 382, 19, "听镇长报案，穿过主街，解救酒馆人质。", ivory);
            button(k, 70, 455, 225, "开始巡街   ↵", true);
            button(k, 308, 455, 185, tv ? "输入 · TVGun" : "输入 · 鼠标", false);
        } else if (g.paused) {
            k.text(68, 215, 54, "已暂停", ivory);
            k.text(70, 332, 21, tv && !locked ? "等待手机重新定位画框" : "按 Esc 或点击继续", ivory);
            button(k, 70, 455, 225, "继续巡街", true);
            button(k, 308, 455, 185, "返回标题", false);
        } else {
            k.text(68, 212, 54, g.screen == Screen::complete ? "人质已获救" : "副警长倒下了", ivory);
            k.text(70, 320, 25,
                   "得分  " + std::to_string(g.score) + "     完成  " + std::to_string(g.hits) + " / 6",
                   gold);
            k.text(70, 373, 18,
                   "命中率 " + std::to_string(g.shots ? 100 * g.hits / g.shots : 0) + "%    受伤 " +
                       std::to_string(g.injuries) + " 次    平均反应 " +
                       std::to_string(g.hits ? g.responseFrames * 1000 / (24 * g.hits) : 0) + " ms",
                   ivory);
            button(k, 70, 455, 225, g.screen == Screen::complete ? "重新巡街" : "从本站续关", true);
            button(k, 308, 455, 185, g.screen == Screen::complete ? "返回标题" : "从头开始", false);
        }
        k.text(70, 606, 16, "左键开火    右键换弹    Esc 暂停    F11 全屏", ivory);
        k.text(70, 642, 16,
               notice.empty()
                   ? (tv ? "TVGun 模式 · 手机与电脑需在同一局域网" : "F2 切换输入设备    C 切换字幕")
                   : notice,
               gold);
        return;
    }
    const auto &c = *g.clip;
    const float left = l.video.x + 24, top = l.video.y + 20, right = l.video.x + l.video.w - 24,
                bottom = l.video.y + l.video.h - 18;
    k.box(left, top, 206, 37, dark);
    k.box(left, top, 3, 37, gold);
    k.text(left + 13, top + 6, 17, chapter(g), ivory);
    if (c.id.starts_with("A0")) {
        k.text(right - 182, top + 6, 16,
               c.id.starts_with("A0_mayor") ? "空格  跳过开场" : "正在进入主街", ivory);
        if (subs && c.id == "A0_mayor_appeal" && g.frame < 147) {
            std::string line =
                g.frame < 67 ? "副警长，黑帽帮在抢银行！" : "快去主街，镇上的人就靠你了。";
            k.box(395, bottom - 72, 490, 48, dark);
            k.text(640, bottom - 65, 24, line, ivory, true);
        }
    } else if (c.id != "D01_badge") {
        k.box(right - 262, top, 262, 40, dark);
        k.text(right - 250, top + 7, 18,
               "生命 " + std::to_string(g.lives) + " / 3     弹药 " + std::to_string(g.ammo) + " / 6",
               ivory);
        k.box(left, bottom - 37, 219, 37, dark);
        k.text(left + 12, bottom - 32, 17,
               "积分 " + std::to_string(g.score) + "    连击 " + std::to_string(g.combo), gold);
        std::string tip;
        if (c.civilian)
            tip = "店员正在过街  ·  请勿开火";
        else if (c.beat == "porch")
            tip = "点金色星徽解救人质  ·  避开红色保护标记";
        else if (c.beat == "wagon")
            tip = "左键开火  ·  右键换弹";
        if (g.reloadTime > 0)
            tip = "正在换弹";
        else if (!g.ammo)
            tip = "弹仓已空  ·  右键换弹";
        if (!tip.empty()) {
            k.box(383, bottom - 37, 514, 37, dark);
            k.text(640, bottom - 32, 17, tip, ivory, true);
        }
        if (c.beat == "porch" && g.enabled(g.frame)) {
            auto p = l.fromVideo(g.level.rescue), q = l.fromVideo(g.level.protect);
            int radius = int(30 * l.video.w / 1280);
            k.ring(p, radius, gold);
            k.star(p, radius - 6, gold);
            k.ring(q, radius, red);
            k.text(float(q.x), float(q.y) - 15, 21, "!", red, true);
        } else if (c.expires >= 0 && !g.expired) {
            auto p = l.fromVideo(c.point);
            int radius = 16 + int(18 * (c.expires - g.frame) / double(c.expires - c.start));
            k.ring(p, radius, gold);
        }
        if (g.feedbackTime > 0) {
            std::string msg;
            switch (g.feedback) {
            case Feedback::hurt:
                msg = "受到攻击";
                break;
            case Feedback::civilian:
                msg = "误伤平民";
                break;
            case Feedback::hit:
                msg = "命中";
                break;
            case Feedback::miss:
                msg = "落空";
                break;
            case Feedback::rescue:
                msg = "解救成功";
                break;
            case Feedback::bonus:
                msg = "平民安全  +500";
                break;
            case Feedback::empty:
                msg = "空仓";
                break;
            default:
                break;
            }
            if (!msg.empty()) {
                k.box(553, top, 174, 38, dark);
                k.text(640, top + 6, 19, msg,
                       g.feedback == Feedback::hurt || g.feedback == Feedback::civilian ? red : gold,
                       true);
            }
            if (g.feedback == Feedback::hurt || g.feedback == Feedback::civilian) {
                int alpha = std::min(135, int(210 * g.feedbackTime));
                SDL_Color glow{185, 38, 26, Uint8(alpha)};
                k.box(l.video.x, l.video.y, l.video.w, 8, glow);
                k.box(l.video.x, l.video.y + l.video.h - 8, l.video.w, 8, glow);
                if (g.feedback == Feedback::hurt && g.feedbackTime > .54 && c.expires >= 0) {
                    auto p = l.fromVideo(c.point);
                    k.star(p, 15, gold);
                }
            }
        }
    }
    if ((!tv || locked) && cursor.x >= 0 && cursor.x < 1280 && cursor.y >= 0 && cursor.y < 720) {
        k.ring(cursor, 9, ivory);
        k.line(cursor.x - 14, cursor.y, cursor.x - 6, cursor.y, ivory);
        k.line(cursor.x + 6, cursor.y, cursor.x + 14, cursor.y, ivory);
    }
}
} // namespace dc
