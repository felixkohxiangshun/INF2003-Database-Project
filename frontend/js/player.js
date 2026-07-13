async function playTrack(track, countNode) {
  State.nowPlaying = track;
  const player = $("#player");
  player.dataset.empty = "false";
  player.classList.add("is-playing");
  $("#player-title").textContent = track.title;
  $("#player-artist").textContent = track.artist;
  $("#player-cover").textContent = "♪";
  $("#player-toggle").disabled = false;
  $("#player-toggle").textContent = "⏸";

  try {
    // play_count comes back from the server since the SQL trigger bumps it, not us
    const result = await API.play(track.track_id);
    const play_count = result?.play_count ?? null;

    const pcNode = $("#player-playcount");
    if (play_count !== null) {
      track.play_count = play_count;
      pcNode.textContent = fmtCount(play_count);
      bump(pcNode);
      if (countNode) { countNode.textContent = fmtCount(play_count); bump(countNode); }
    } else {
      // /play not yet implemented — show existing count without crashing
      pcNode.textContent = fmtCount(track.play_count ?? 0);
    }
  } catch (err) {
    toast(err.message, "err");
  }
}

function bump(node) { node.classList.remove("bump"); void node.offsetWidth; node.classList.add("bump"); }

function setupPlayer() {
  $("#player-toggle").addEventListener("click", () => {
    const player = $("#player");
    const playing = player.classList.toggle("is-playing");
    $("#player-toggle").textContent = playing ? "⏸" : "▶";
  });
}
