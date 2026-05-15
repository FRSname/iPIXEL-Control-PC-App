#pragma once
#include "config.h"

void webUiBegin(AppConfig& cfgRef);

// Latest fetched count, surfaced on the web UI's status page.
void webUiSetStatus(const String& username, uint32_t count, const String& lastError);
