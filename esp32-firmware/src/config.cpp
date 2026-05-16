#include "config.h"
#include <Preferences.h>

static const char* NS = "ipx";

void configLoad(AppConfig& c) {
    Preferences p;
    p.begin(NS, true);
    c.igUserId    = p.getString("ig_id", "");
    c.accessToken = p.getString("ig_tok", "");
    c.refreshSec  = p.getUInt("refresh", 300);
    c.formatMode  = p.getUChar("fmt", 0);
    c.textColor   = p.getUInt("fg", 0xFFFFFF);
    c.bgColor     = p.getUInt("bg", 0x000000);
    c.panelMac    = p.getString("mac", "");
    c.rotate180   = p.getBool("rot180", false);
    p.end();
    if (c.refreshSec < 60) c.refreshSec = 60;
}

void configSave(const AppConfig& c) {
    Preferences p;
    p.begin(NS, false);
    p.putString("ig_id", c.igUserId);
    p.putString("ig_tok", c.accessToken);
    p.putUInt("refresh", c.refreshSec < 60 ? 60 : c.refreshSec);
    p.putUChar("fmt", c.formatMode);
    p.putUInt("fg", c.textColor);
    p.putUInt("bg", c.bgColor);
    p.putString("mac", c.panelMac);
    p.putBool("rot180", c.rotate180);
    p.end();
}

bool configIsProvisioned(const AppConfig& c) {
    return c.igUserId.length() > 0 && c.accessToken.length() > 0;
}
