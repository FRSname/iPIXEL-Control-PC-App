#pragma once
#include <Arduino.h>

struct IgResult {
    bool     ok;
    uint32_t followerCount;
    String   username;
    String   error;     // populated when ok == false
};

// Blocking HTTPS GET to the Instagram Graph API. Call from a FreeRTOS task,
// not from the Arduino loop or any web-server callback.
IgResult igFetchFollowers(const String& igUserId, const String& accessToken);
