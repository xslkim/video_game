#include "game.hpp"
#include "tvgun.hpp"
#include <iostream>
#include <thread>
using namespace dc;
static void require(bool v, const std::string &why) {
    if (!v)
        throw std::runtime_error(why);
}
static void click(Game &g, Point p) { g.shoot(p, g.generation, g.frame); }
static void done(Game &g) { g.present(g.clip->frames); }
static void active(Game &g, const std::string &id) {
    g.enter(id);
    g.present(g.clip->opens);
}
static Point sample(const Clip &c, int f) {
    auto &s = c.masks.at(f);
    require(!s.empty(), "missing visible spans: " + c.id);
    auto a =
        *std::max_element(s.begin(), s.end(), [](auto a, auto b) { return a.x1 - a.x0 < b.x1 - b.x0; });
    return {double(a.x0 + a.x1), a.y * 2. + 1};
}
static void rules(const Level &l) {
    Game g(l);
    g.start();
    g.skip();
    require(g.clip->id == "A0_travel_main", "skip");
    done(g);
    g.present(g.clip->opens - 1);
    click(g, g.clip->point);
    require(g.ammo == 6, "early input");
    g.present(g.clip->opens);
    int prev = g.generation;
    click(g, sample(*g.clip, g.frame));
    require(g.hits == 1 && g.clip->id == "A1_change_barrels", "early branch");
    g.shoot({500, 300}, prev, 21);
    require(g.ammo == 5, "duplicate previous round");
    g.present(g.clip->opens);
    click(g, sample(*g.clip, g.frame));
    require(g.hits == 2 && g.clip->id == "A1_exit_barrels", "merged branch");
    active(g, "A1_threat_barrels");
    for (int i = 0; i < 4; i++)
        click(g, {20, 20});
    require(g.ammo == 0 && g.combo == 0, "miss and empty");
    int shots = g.shots;
    click(g, {20, 20});
    require(g.shots == shots, "empty count");
    g.reload();
    g.tick(.25);
    g.reload();
    require(g.reloadTime == .25, "reload reset");
    g.paused = true;
    g.tick(1.);
    click(g, g.clip->point);
    require(g.reloadTime == .25, "pause");
    g.paused = false;
    g.tick(.25);
    require(g.ammo == 6, "reload completion");
    active(g, "A1_threat_wagon");
    g.lives = 1;
    g.present(g.clip->expires);
    g.present(g.frame + 1);
    click(g, g.clip->point);
    require(g.lives == 1 && g.injuries == 1 && g.expired, "tutorial or double deadline");
    done(g);
    require(g.speed() == .8 && !g.expired, "mercy retry");
    active(g, "A3_cross_clerk");
    g.lives = 3;
    g.present(36);
    auto protectedPoint = sample(*g.clip, g.frame);
    click(g, protectedPoint);
    click(g, protectedPoint);
    require(g.lives == 2, "clerk penalized twice");
    int score = g.score;
    done(g);
    require(g.score == score, "bonus after shot");
    active(g, "A3_cross_clerk");
    done(g);
    require(g.score == score + 500, "clean cross");
    active(g, "A4_threat_porch");
    click(g, {330, 438});
    require(g.lives == 2 && g.hits == 2 && g.clip->id == "A4_threat_porch", "neutral scenery");
    click(g, l.protect);
    require(g.lives == 1 && g.clip->id == "A4_scare", "scare branch");
    done(g);
    click(g, l.protect);
    require(g.lives == 0 && g.clip->id == "D01_badge", "death priority");
    done(g);
    require(g.screen == Screen::failed, "failed screen");
    g.start(true);
    require(g.ammo == 6 && g.lives == 3 && g.hits == 0 && g.clip->id == "A4_enter_porch", "checkpoint");
    active(g, "A4_threat_porch");
    click(g, l.rescue);
    int bullets = g.ammo;
    g.present(47);
    click(g, {630, 310});
    g.reload();
    require(g.ammo == bullets && !g.reloadTime, "terminal input");
    done(g);
    require(g.screen == Screen::complete, "complete screen");
    g.start();
    require(g.clip->id == "A0_mayor_arrives" && g.score == 0, "restart");
    active(g, "A3_threat_store");
    g.present(30);
    require(g.clip->covers(30, {530, 460}), "money bag should count");
    g.lives = 1;
    g.present(g.clip->expires);
    require(g.clip->id == "D01_badge", "timeout death");
    done(g);
    g.start(true);
    require(g.clip->id == "A3_cross_clerk", "restart at store civilian");
    for (const auto &[id, c] : l.clips) {
        if (c.expires < 0)
            continue;
        g.start();
        active(g, id);
        g.present(c.expires - 1);
        int hits = g.hits;
        click(g, c.beat == "porch" ? l.rescue : sample(c, g.frame));
        require(g.hits == hits + 1, "last valid frame " + id);
        active(g, id);
        g.present(c.expires);
        hits = g.hits;
        click(g, c.point);
        require(hits == g.hits, "timeout frame " + id);
    }
}
static std::array<int, 4> runAt(const Level &l, int hz, bool late) {
    Game g(l);
    g.start();
    int gen = -1;
    double local = 0;
    for (int tick = 0; tick < hz * 90 && g.screen == Screen::play; ++tick) {
        if (gen != g.generation) {
            gen = g.generation;
            local = g.frame;
        }
        g.tick(1. / hz);
        g.present(int(local));
        if (g.clip->expires >= 0 && g.enabled(g.frame) &&
            g.frame >= (late ? g.clip->expires - 3 : g.clip->opens + 5)) {
            click(g, g.clip->beat == "porch" ? l.rescue : sample(*g.clip, g.frame));
        }
        local += 24. / hz;
    }
    require(g.screen == Screen::complete && g.hits == 6, "full route");
    return {g.hits, g.lives, g.score, g.shots};
}
static void protocol() {
    Receiver receiver;
    int shots = 0, reloads = 0, lost = 0, specials = 0;
    Point shot{};
    auto notify = [&](RemoteAction a, Point p) {
        if (a == RemoteAction::shoot) {
            ++shots;
            shot = p;
        }
        if (a == RemoteAction::reload)
            ++reloads;
        if (a == RemoteAction::lost)
            ++lost;
        if (a == RemoteAction::special)
            ++specials;
    };
    auto send = [&](std::string msg, int ms) { receiver.process(msg, "handset", ms, notify); };
    send("HELLO test-session-one", 1);
    send("120,220,4,5", 4);
    send("130,230,4,8", 5);
    send("SPECIAL", 5);
    require(specials == 1, "Locked handset delivers SPECIAL");
    send("SHOT 150,240,7", 6);
    send("SHOT 150,240,7", 7);
    require(shots == 1 && shot.x == 150, "UDP coordinates / duplicate / reorder");
    send("LOST,10", 8);
    send("SPECIAL", 8);
    require(specials == 1, "Lost handset cannot deliver SPECIAL");
    send("SHOT 3,4,9", 9);
    send("4,5,4,13", 10);
    send("SHOT 3,4,9", 11);
    require(shots == 1 && lost == 1, "late after loss");
    send("RELOAD", 12);
    require(reloads == 1, "explicit reload");
    receiver.fence();
    send("SHOT 1,2,12", 13);
    require(shots == 1, "stale at scene cut");
    send("HELLO test-session-two", 15);
    send("HELLO test-session-one", 16);
    send("10,10,4,1", 18);
    send("SHOT", 40);
    require(shots == 2, "session recovery");
    send("SHOT", 151);
    require(shots == 2, "stale bare shot");
}
static void udpLoopback() {
    Receiver rx;
    require(rx.open(0, 0), "UDP loopback socket");
    SOCKET client = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    require(client != INVALID_SOCKET, "UDP client");
    DWORD timeout = 1000;
    setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<char *>(&timeout), sizeof(timeout));
    int shots = 0;
    auto notify = [&](RemoteAction a, Point) { shots += a == RemoteAction::shoot; };
    auto send = [&](int port, std::string msg) {
        sockaddr_in dst{};
        dst.sin_family = AF_INET;
        dst.sin_port = htons(port);
        dst.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        sendto(client, msg.data(), int(msg.size()), 0, reinterpret_cast<sockaddr *>(&dst), sizeof(dst));
        for (int i = 0; i < 4; ++i) {
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
            rx.poll(100, notify);
        }
    };
    auto reply = [&]() {
        char b[80];
        int n = recv(client, b, 80, 0);
        return n > 0 ? std::string(b, n) : "";
    };
    send(rx.discoveryPort(), "TVGUN_DISCOVER");
    require(reply() == "TVGUN_HERE " + std::to_string(rx.gamePort()), "discovery");
    send(rx.gamePort(), "HELLO loopback-session");
    require(reply() == "FRAME 24,48", "frame");
    send(rx.gamePort(), "400,300,4,1");
    send(rx.gamePort(), "SHOT 400,300,2");
    send(rx.gamePort(), "SHOT 400,300,2");
    require(shots == 1, "UDP socket trigger");
    rx.poll(900, notify);
    require(!rx.hasLock(), "lock timeout");
    closesocket(client);
}
int main(int argc, char **argv) {
    try {
        require(argc >= 2, "level dir required");
        Level l(fs::u8path(argv[1]));
        rules(l);
        for (bool late : {false, true})
            require(runAt(l, 30, late) == runAt(l, 60, late), "30/60 Hz replay diverged");
        protocol();
        udpLoopback();
        std::cout
            << "PASS: six encounters, both endings, replay at 30/60 Hz, UDP protocol and loopback\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << "\n";
        return 1;
    }
}
