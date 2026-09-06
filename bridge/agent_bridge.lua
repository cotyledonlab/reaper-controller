-- agent_bridge.lua — in-REAPER Lua daemon for reaper-controller (protocol v1).
--
-- Install: copy to <ResourcePath>/Scripts/agent_bridge.lua, then in REAPER:
--   Actions -> Show action list -> New action... -> Load ReaScript -> pick it -> Run.
--   (Optional persistent start: SWS Extensions -> Startup actions -> set as global startup action.)
-- The daemon never steals focus, never opens windows; failures go to out/<id>.json, never popups.
--
-- How it works: a reaper.defer loop scans AgentBridge/in/*.json ~10x/sec,
-- executes the op against the ReaScript API, and writes AgentBridge/out/<id>.json
-- atomically (tmp + rename). Host deletes both files after reading the reply.
-- Ops v1: ping, hello. Unknown ops answer ok=false, code=UNKNOWN_OP.

local RES = reaper.GetResourcePath()
local IN_DIR = RES .. '/AgentBridge/in'
local OUT_DIR = RES .. '/AgentBridge/out'
local LOG_DIR = RES .. '/AgentBridge/log'
local HEARTBEAT = LOG_DIR .. '/heartbeat.txt'

---------------------------------------------------------------
-- minimal JSON (objects/arrays/strings/numbers/bool/null).
-- \u escapes above U+007F decode as '?' (host params are ASCII in practice).
---------------------------------------------------------------
local json = {}

function json.encode(v)
  local t = type(v)
  if t == 'nil' then return 'null'
  elseif t == 'boolean' then return v and 'true' or 'false'
  elseif t == 'number' then
    if v ~= v or v == math.huge or v == -math.huge then return 'null' end
    return tostring(v)
  elseif t == 'string' then
    return '"' .. v:gsub('[%z\1-\31\\"]', function(c)
      if c == '"' then return '\\"'
      elseif c == '\\' then return '\\\\'
      elseif c == '\n' then return '\\n'
      elseif c == '\r' then return '\\r'
      elseif c == '\t' then return '\\t'
      elseif c == '\b' then return '\\b'
      elseif c == '\f' then return '\\f'
      else return string.format('\\u%04x', string.byte(c)) end
    end) .. '"'
  elseif t == 'table' then
    local is_arr, n = true, 0
    for k, _ in pairs(v) do
      n = n + 1
      if type(k) ~= 'number' or k ~= n then is_arr = false end
    end
    local parts = {}
    if is_arr then
      for i = 1, n do parts[#parts + 1] = json.encode(v[i]) end
      return '[' .. table.concat(parts, ',') .. ']'
    else
      local keys = {}
      for k, _ in pairs(v) do keys[#keys + 1] = k end
      table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
      for _, k in ipairs(keys) do
        parts[#parts + 1] = json.encode(tostring(k)) .. ':' .. json.encode(v[k])
      end
      return '{' .. table.concat(parts, ',') .. '}'
    end
  else
    return 'null'
  end
end

function json.decode(s)
  local pos = 1
  local function err(msg) error('json: ' .. msg .. ' at ' .. pos) end
  local function ws()
    while pos <= #s and s:sub(pos, pos):match('%s') do pos = pos + 1 end
  end
  local parse_value
  local function parse_str()
    pos = pos + 1 -- opening quote
    local out = {}
    while pos <= #s do
      local c = s:sub(pos, pos)
      if c == '"' then pos = pos + 1; return table.concat(out) end
      if c == '\\' then
        local e = s:sub(pos + 1, pos + 1)
        if e == 'n' then out[#out + 1] = '\n'
        elseif e == 'r' then out[#out + 1] = '\r'
        elseif e == 't' then out[#out + 1] = '\t'
        elseif e == 'b' then out[#out + 1] = '\b'
        elseif e == 'f' then out[#out + 1] = '\f'
        elseif e == 'u' then
          local hex = s:sub(pos + 2, pos + 5)
          local cp = tonumber(hex, 16)
          if not cp then err('bad \\u escape') end
          out[#out + 1] = cp < 0x80 and string.char(cp) or '?'
          pos = pos + 4
        else out[#out + 1] = e end
        pos = pos + 2
      else
        out[#out + 1] = c; pos = pos + 1
      end
    end
    err('unterminated string')
  end
  local function parse_num()
    local m = s:sub(pos):match('^-?%d+%.?%d*[eE]?[+-]?%d*')
    if not m or #m == 0 then err('bad number') end
    pos = pos + #m
    local n = tonumber(m)
    if not n then err('bad number') end
    return n
  end
  parse_value = function()
    ws()
    local c = s:sub(pos, pos)
    if c == '{' then
      pos = pos + 1
      local o = {}
      ws()
      if s:sub(pos, pos) == '}' then pos = pos + 1; return o end
      while true do
        ws()
        if s:sub(pos, pos) ~= '"' then err('expected string key') end
        local k = parse_str()
        ws()
        if s:sub(pos, pos) ~= ':' then err("expected ':'") end
        pos = pos + 1
        o[k] = parse_value()
        ws()
        local d = s:sub(pos, pos)
        if d == '}' then pos = pos + 1; return o end
        if d ~= ',' then err("expected ','") end
        pos = pos + 1
      end
    elseif c == '[' then
      pos = pos + 1
      local a = {}
      ws()
      if s:sub(pos, pos) == ']' then pos = pos + 1; return a end
      while true do
        a[#a + 1] = parse_value()
        ws()
        local d = s:sub(pos, pos)
        if d == ']' then pos = pos + 1; return a end
        if d ~= ',' then err("expected ','") end
        pos = pos + 1
      end
    elseif c == '"' then return parse_str()
    elseif c == 't' and s:sub(pos, pos + 3) == 'true' then pos = pos + 4; return true
    elseif c == 'f' and s:sub(pos, pos + 4) == 'false' then pos = pos + 5; return false
    elseif c == 'n' and s:sub(pos, pos + 3) == 'null' then pos = pos + 4; return nil
    else return parse_num() end
  end
  local v = parse_value()
  ws()
  if pos <= #s then err('trailing data') end
  return v
end

---------------------------------------------------------------
-- bridge
---------------------------------------------------------------
reaper.RecursiveCreateDirectory(IN_DIR, 0)
reaper.RecursiveCreateDirectory(OUT_DIR, 0)
reaper.RecursiveCreateDirectory(LOG_DIR, 0)

SHUTDOWN = false
math.randomseed(os.time())

-- find first MIDI take on a track, or the take in item `item_idx` (0-based)
local function find_take(track_idx, item_idx)
  local tr = reaper.GetTrack(0, track_idx or 0)
  if not tr then return nil, 'NO_TRACK' end
  local n = reaper.CountTrackMediaItems(tr)
  for i = 0, n - 1 do
    local it = reaper.GetTrackMediaItem(tr, i)
    if it and (item_idx == nil or reaper.GetMediaItemInfo_Value(it, 'IP_ITEMNUMBER') == item_idx) then
      local take = reaper.GetActiveTake(it)
      if take and reaper.TakeIsMIDI(take) then return take end
      if item_idx ~= nil then return nil, 'NO_MIDI_TAKE' end
    end
  end
  return nil, 'NO_MIDI_TAKE'
end

-- single-instance guard: a live sibling refreshes this extstate every beat.
-- (v1 daemon has no guard, so upgrading from v1 needs a REAPER restart.)
local last_ext = tonumber(reaper.GetExtState('agent_bridge', 'heartbeat') or '0') or 0
if os.time() - last_ext < 15 then return end

local function read_file(p)
  local f = io.open(p, 'r')
  if not f then return nil end
  local s = f:read('*a')
  f:close()
  return s
end

local function write_atomic(p, s)
  local tmp = p .. '.tmp'
  local f = io.open(tmp, 'w')
  if not f then return false end
  f:write(s)
  f:close()
  os.rename(tmp, p)
  return true
end

local function reply_ok(op_id, result, evidence)
  write_atomic(OUT_DIR .. '/' .. op_id .. '.json', json.encode({
    v = 1, op_id = op_id, ok = true, result = result or {},
    adapter = 'reascript-lua', evidence = evidence or {},
  }))
end

local function reply_err(op_id, code, detail)
  write_atomic(OUT_DIR .. '/' .. op_id .. '.json', json.encode({
    v = 1, op_id = op_id, ok = false,
    error = { code = code, detail = detail or '' },
  }))
end

local function handle(op_id, req)
  if type(req) ~= 'table' then reply_err(op_id, 'BAD_REQUEST', 'unparseable JSON'); return end
  if req.v ~= 1 then reply_err(op_id, 'BAD_VERSION', 'expected v=1'); return end
  if req.op_id ~= op_id then reply_err(op_id, 'ID_MISMATCH', 'filename/op_id differ'); return end
  local op = req.op
  if op == 'ping' then
    reply_ok(op_id, { pong = true }, { 'op:ping' })
  elseif op == 'hello' then
    reply_ok(op_id, {
      app_version = reaper.GetAppVersion(),
      tracks = reaper.CountTracks(0),
      state_change_count = reaper.GetProjectStateChangeCount(0),
    }, { 'op:hello' })
  elseif op == 'bridge.shutdown' then
    reply_ok(op_id, { stopping = true }, { 'op:bridge.shutdown' })
    SHUTDOWN = true
  elseif op == 'engineer.add_track' then
    local p = req.params or {}
    local idx = reaper.CountTracks(0)
    reaper.InsertTrackAtIndex(idx, true)
    local tr = reaper.GetTrack(0, idx)
    if not tr then reply_err(op_id, 'NO_TRACK', 'insert failed'); return end
    if p.name and p.name ~= '' then
      reaper.GetSetMediaTrackInfo_String(tr, 'P_NAME', p.name, true)
    end
    reply_ok(op_id, { index = idx, guid = reaper.GetTrackGUID(tr) },
      { 'op:engineer.add_track', 'index:' .. idx })
  elseif op == 'engineer.add_fx' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track ' .. tostring(p.track)); return end
    local idx = reaper.TrackFX_AddByName(tr, p.fx or 'ReaSynth', false, 1)
    if idx < 0 then
      reply_err(op_id, 'FX_NOT_FOUND', tostring(p.fx or 'ReaSynth'))
      return
    end
    local _, name = reaper.TrackFX_GetFXName(tr, idx, '')
    reply_ok(op_id, { fx_index = idx, name = name },
      { 'op:engineer.add_fx', 'fx:' .. name })
  elseif op == 'player.insert_midi' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track ' .. tostring(p.track)); return end
    local start_sec, len_sec = p.start_sec or 0, p.length_sec or 8
    local item = reaper.CreateNewMIDIItemInProj(tr, start_sec, start_sec + len_sec, false)
    if not item then reply_err(op_id, 'NO_ITEM', 'midi item create failed'); return end
    local take = reaper.GetActiveTake(item)
    if not take or not reaper.TakeIsMIDI(take) then
      reply_err(op_id, 'NO_TAKE', 'no midi take'); return
    end
    local qn0 = reaper.TimeMap2_timeToQN(0, start_sec)
    local n = 0
    for _, nt in ipairs(p.notes or {}) do
      local qs = qn0 + (nt.start_beats or 0)
      local qe = qs + (nt.dur_beats or 1)
      reaper.MIDI_InsertNote(take, false, false,
        reaper.MIDI_GetPPQPosFromProjQN(take, qs),
        reaper.MIDI_GetPPQPosFromProjQN(take, qe),
        nt.chan or 0, nt.pitch or 60, nt.vel or 96, true)
      n = n + 1
    end
    reaper.MIDI_Sort(take)
    reply_ok(op_id, {
      item_index = reaper.GetMediaItemInfo_Value(item, 'IP_ITEMNUMBER'),
      notes = n,
    }, { 'op:player.insert_midi', 'notes:' .. n })
  elseif op == 'project.set_render' then
    local path = (req.params or {}).path or ''
    reaper.GetSetProjectInfo_String(0, 'RENDER_FILE', path, true)
    local _, back = reaper.GetSetProjectInfo_String(0, 'RENDER_FILE', '', false)
    reply_ok(op_id, { requested = path, readback = back },
      { 'op:project.set_render' })
  elseif op == 'engineer.get_mix' then
    local tr = reaper.GetTrack(0, (req.params or {}).track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    local vol = reaper.GetMediaTrackInfo_Value(tr, 'D_VOL')
    local pan = reaper.GetMediaTrackInfo_Value(tr, 'D_PAN')
    local mute = reaper.GetMediaTrackInfo_Value(tr, 'B_MUTE') >= 0.5
    local solo = reaper.GetMediaTrackInfo_Value(tr, 'B_SOLO') ~= 0
    reply_ok(op_id, { volume = vol, pan = pan, mute = mute, solo = solo },
      { 'op:engineer.get_mix', 'observed:mix' })
  elseif op == 'engineer.set_volume' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    reaper.SetMediaTrackInfo_Value(tr, 'D_VOL', p.value or 1)
    local observed = reaper.GetMediaTrackInfo_Value(tr, 'D_VOL')
    reply_ok(op_id, { requested = p.value, observed = observed },
      { 'op:engineer.set_volume', 'observed:' .. observed })
  elseif op == 'engineer.set_pan' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    reaper.SetMediaTrackInfo_Value(tr, 'D_PAN', p.value or 0)
    local observed = reaper.GetMediaTrackInfo_Value(tr, 'D_PAN')
    reply_ok(op_id, { requested = p.value, observed = observed },
      { 'op:engineer.set_pan', 'observed:' .. observed })
  elseif op == 'engineer.set_mute' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    reaper.SetMediaTrackInfo_Value(tr, 'B_MUTE', p.mute and 1 or 0)
    local observed = reaper.GetMediaTrackInfo_Value(tr, 'B_MUTE') >= 0.5
    reply_ok(op_id, { requested = not not p.mute, observed = observed },
      { 'op:engineer.set_mute', 'observed:' .. tostring(observed) })
  elseif op == 'engineer.fx_list' then
    local tr = reaper.GetTrack(0, (req.params or {}).track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    local out = {}
    for i = 0, reaper.TrackFX_GetCount(tr) - 1 do
      local _, name = reaper.TrackFX_GetFXName(tr, i, '')
      out[#out + 1] = { index = i, name = name,
        params = reaper.TrackFX_GetNumParams(tr, i) }
    end
    reply_ok(op_id, { fx = out }, { 'op:engineer.fx_list', 'observed:fx' })
  elseif op == 'engineer.fx_get_param' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    local val = reaper.TrackFX_GetParamNormalized(tr, p.fx or 0, p.param or 0)
    reply_ok(op_id, { value = val }, { 'op:engineer.fx_get_param', 'observed:' .. tostring(val) })
  elseif op == 'engineer.fx_set_param' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    reaper.TrackFX_SetParamNormalized(tr, p.fx or 0, p.param or 0, p.value or 0)
    local observed = reaper.TrackFX_GetParamNormalized(tr, p.fx or 0, p.param or 0)
    reply_ok(op_id, { requested = p.value, observed = observed },
      { 'op:engineer.fx_set_param', 'observed:' .. tostring(observed) })
  elseif op == 'engineer.fx_param_names' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    local total = reaper.TrackFX_GetNumParams(tr, p.fx or 0)
    local from, names = p.from or 0, {}
    local upto = math.min(total, from + (p.count or total))
    for i = from, upto - 1 do
      local _, name = reaper.TrackFX_GetParamName(tr, p.fx or 0, i, '')
      names[#names + 1] = { index = i, name = name }
    end
    reply_ok(op_id, { total = total, from = from, names = names },
      { 'op:engineer.fx_param_names', 'observed:total=' .. total })
  elseif op == 'player.quantize' then
    local p = req.params or {}
    local take, err = find_take(p.track or 0, p.item)
    if not take then reply_err(op_id, err, 'no midi take'); return end
    local grid = p.grid_beats or 0.25
    local _, count = reaper.MIDI_CountEvts(take)
    local fixed, maxdev = 0, 0
    for i = 0, count - 1 do
      local _, sel, muted, s, e, ch, pitch, vel = reaper.MIDI_GetNote(take, i)
      local qn = reaper.MIDI_GetProjQNFromPPQPos(take, s)
      local q = math.floor(qn / grid + 0.5) * grid
      local dev = math.abs(qn - q)
      if dev > 1e-9 then
        local ns = reaper.MIDI_GetPPQPosFromProjQN(take, q)
        reaper.MIDI_SetNote(take, i, sel, muted, ns, ns + (e - s), ch, pitch, vel, true)
        fixed = fixed + 1
        if dev > maxdev then maxdev = dev end
      end
    end
    reaper.MIDI_Sort(take)
    reply_ok(op_id, { notes = count, fixed = fixed, max_dev_beats = maxdev },
      { 'op:player.quantize', 'observed:fixed=' .. fixed })
  elseif op == 'player.humanize' then
    local p = req.params or {}
    local take, err = find_take(p.track or 0, p.item)
    if not take then reply_err(op_id, err, 'no midi take'); return end
    local t_amt, v_amt = p.timing_beats or 0.02, p.vel_amount or 6
    local _, count = reaper.MIDI_CountEvts(take)
    local vlo, vhi = 127, 0
    for i = 0, count - 1 do
      local _, sel, muted, s, e, ch, pitch, vel = reaper.MIDI_GetNote(take, i)
      local off = (math.random() * 2 - 1) * t_amt * 960
      local nv = math.max(1, math.min(127, math.floor(vel + (math.random() * 2 - 1) * v_amt + 0.5)))
      reaper.MIDI_SetNote(take, i, sel, muted, s + off, e + off, ch, pitch, nv, true)
      if nv < vlo then vlo = nv end
      if nv > vhi then vhi = nv end
    end
    reaper.MIDI_Sort(take)
    reply_ok(op_id, { notes = count, vel_min = vlo, vel_max = vhi },
      { 'op:player.humanize', 'observed:vel_spread=' .. vlo .. '-' .. vhi })
  elseif op == 'engineer.set_folder' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    reaper.SetMediaTrackInfo_Value(tr, 'I_FOLDERDEPTH', p.depth or 0)
    local observed = reaper.GetMediaTrackInfo_Value(tr, 'I_FOLDERDEPTH')
    reply_ok(op_id, { requested = p.depth or 0, observed = observed },
      { 'op:engineer.set_folder', 'observed:' .. observed })
  elseif op == 'engineer.add_send' then
    local p = req.params or {}
    local src = reaper.GetTrack(0, p.from or 0)
    local dst = reaper.GetTrack(0, p.to or 0)
    if not src or not dst then reply_err(op_id, 'NO_TRACK', 'bad from/to'); return end
    local idx = reaper.CreateTrackSend(src, dst)
    if idx < 0 then reply_err(op_id, 'SEND_FAILED', 'create failed'); return end
    if p.volume ~= nil then reaper.SetTrackSendInfo_Value(src, 0, idx, 'D_VOL', p.volume) end
    local vol = reaper.GetTrackSendInfo_Value(src, 0, idx, 'D_VOL')
    reply_ok(op_id, { send_index = idx, observed_volume = vol },
      { 'op:engineer.add_send', 'observed_vol:' .. tostring(vol) })
  elseif op == 'engineer.list_sends' then
    local tr = reaper.GetTrack(0, (req.params or {}).track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    local out = {}
    for i = 0, reaper.GetTrackNumSends(tr, 0) - 1 do
      local dest = reaper.GetTrackSendInfo_Value(tr, 0, i, 'P_DESTTRACK')
      local destn = dest and (reaper.GetMediaTrackInfo_Value(dest, 'IP_TRACKNUMBER') - 1) or nil
      out[#out + 1] = {
        index = i, dest_track = destn,
        volume = reaper.GetTrackSendInfo_Value(tr, 0, i, 'D_VOL'),
        mute = reaper.GetTrackSendInfo_Value(tr, 0, i, 'B_MUTE') ~= 0,
      }
    end
    reply_ok(op_id, { sends = out }, { 'op:engineer.list_sends', 'observed:sends' })
  elseif op == 'project.add_marker' then
    local p = req.params or {}
    local idx = reaper.AddProjectMarker2(0, false, p.position_sec or 0, 0, p.name or '', -1, 0)
    reply_ok(op_id, { marker_index = idx }, { 'op:project.add_marker', 'observed:idx=' .. idx })
  elseif op == 'project.list_markers' then
    local out, i = {}, 0
    while true do
      local ret, isrgn, pos, rgnend, name, num = reaper.EnumProjectMarkers3(0, i)
      if ret == 0 then break end
      if not isrgn then
        out[#out + 1] = { index = i, position_sec = pos, name = name, number = num }
      end
      i = i + 1
    end
    reply_ok(op_id, { markers = out }, { 'op:project.list_markers', 'observed:markers' })
  elseif op == 'project.set_loop' then
    local p = req.params or {}
    reaper.GetSet_LoopTimeRange2(0, true, false, p.start_sec or 0, p.end_sec or 4, false)
    local s, e = reaper.GetSet_LoopTimeRange2(0, false, false, 0, 0, false)
    reply_ok(op_id, { requested = { p.start_sec or 0, p.end_sec or 4 }, observed = { s, e } },
      { 'op:project.set_loop', 'observed:' .. s .. '-' .. e })
  elseif op == 'project.get_loop' then
    local s, e = reaper.GetSet_LoopTimeRange2(0, false, false, 0, 0, false)
    reply_ok(op_id, { start_sec = s, end_sec = e }, { 'op:project.get_loop', 'observed:loop' })
  elseif op == 'player.rec_arm' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    if p.armed ~= nil then reaper.SetMediaTrackInfo_Value(tr, 'I_RECARM', p.armed and 1 or 0) end
    if p.monitor ~= nil then reaper.SetMediaTrackInfo_Value(tr, 'I_RECMON', p.monitor and 1 or 0) end
    local armed = reaper.GetMediaTrackInfo_Value(tr, 'I_RECARM') ~= 0
    local mon = reaper.GetMediaTrackInfo_Value(tr, 'I_RECMON') ~= 0
    reply_ok(op_id, { armed = armed, monitor = mon },
      { 'op:player.rec_arm', 'observed:armed=' .. tostring(armed) })
  elseif op == 'engineer.get_input' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    local code = reaper.GetMediaTrackInfo_Value(tr, 'I_RECINPUT')
    local is_midi, dev, chan = false, nil, nil
    if code >= 4096 then
      is_midi = true
      dev = math.floor((code - 4096) / 32)
      chan = (code - 4096) % 32
    end
    local devices = {}
    if reaper.GetMIDIInputName then
      for i = 0, 63 do
        local st, ok, name = pcall(reaper.GetMIDIInputName, i, '')
        if st and ok and name and name ~= '' then
          devices[#devices + 1] = { index = i, name = name }
        end
      end
    end
    reply_ok(op_id, {
      code = code, is_midi = is_midi, device = dev, channel = chan,
      devices = devices,
      armed = reaper.GetMediaTrackInfo_Value(tr, 'I_RECARM') ~= 0,
      monitor = reaper.GetMediaTrackInfo_Value(tr, 'I_RECMON') ~= 0,
    }, { 'op:engineer.get_input', 'observed:input' })
  elseif op == 'player.select_take' then
    local p = req.params or {}
    local tr = reaper.GetTrack(0, p.track or 0)
    if not tr then reply_err(op_id, 'NO_TRACK', 'no track'); return end
    local item, n = nil, reaper.CountTrackMediaItems(tr)
    for i = 0, n - 1 do
      local it = reaper.GetTrackMediaItem(tr, i)
      if it and reaper.GetMediaItemInfo_Value(it, 'IP_ITEMNUMBER') == (p.item or 0) then
        item = it break
      end
    end
    if not item then reply_err(op_id, 'NO_ITEM', 'no item'); return end
    local take = reaper.GetMediaItemTake(item, p.take or 0)
    if not take then reply_err(op_id, 'NO_TAKE', 'no take'); return end
    reaper.SetActiveTake(take)
    local active = reaper.GetActiveTake(item) == take
    reply_ok(op_id, { selected = p.take or 0, active = active },
      { 'op:player.select_take', 'observed:active=' .. tostring(active) })
  elseif op == 'project.save' then
    local path = (req.params or {}).path or ''
    if path == '' then reply_err(op_id, 'BAD_REQUEST', 'path required'); return end
    reaper.Main_SaveProjectEx(0, path, 0)
    reply_ok(op_id, { path = path }, { 'op:project.save' })
  else
    reply_err(op_id, 'UNKNOWN_OP', 'no such op: ' .. tostring(op))
  end
end

local last_scan, last_beat = 0, 0

local function tick()
  local now = reaper.time_precise()
  if now - last_scan >= 0.1 then
    last_scan = now
    local i, guard = 0, 0
    while guard < 500 do
      local fn = reaper.EnumerateFiles(IN_DIR, i)
      if not fn then break end
      i, guard = i + 1, guard + 1
      local op_id = fn:match('^(.-)%.json$')
      if op_id and not io.open(OUT_DIR .. '/' .. op_id .. '.json', 'r') then
        local body = read_file(IN_DIR .. '/' .. fn)
        if body then
          local ok, req = pcall(json.decode, body)
          if ok then
            local st, em = pcall(handle, op_id, req)
            if not st then reply_err(op_id, 'INTERNAL', tostring(em)) end
          else
            reply_err(op_id, 'BAD_REQUEST', tostring(req))
          end
        end
      end
    end
  end
  if now - last_beat >= 5 then
    last_beat = now
    write_atomic(HEARTBEAT, tostring(os.time()) .. '\n')
    reaper.SetExtState('agent_bridge', 'heartbeat', tostring(os.time()), false)
  end
  if SHUTDOWN then return end
  reaper.defer(tick)
end

reaper.defer(tick)
