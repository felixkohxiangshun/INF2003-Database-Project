/* ============================================================
   Resonate — Recommendations view (For You)
   Two sections:
     1. Tracks recommended via Neo4j genre affinity
     2. Artists recommended via Neo4j SIMILAR_TO traversal
   ============================================================ */

async function renderRecommend() {
  const [{ recommendations }, { artists }] = await Promise.all([
    API.recommend(),
    API.recommendArtists(),
  ]);

  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, "powered by neo4j graph traversal"),
    el("h1", {}, "For You"),
    el("p", {}, "Recommended from your listening history."));

  const wrap = el("div", {});
  wrap.append(head);

  // ── Track recommendations ─────────────────────────────────────────────
  const trackSection = el("div", { class: "rec-section" });
  trackSection.append(el("p", { class: "rec-section__label" }, "Tracks · genre affinity"));

  if (!recommendations.length) {
    trackSection.append(el("div", { class: "empty" },
      el("strong", {}, "Nothing yet"),
      "Play a few tracks and recommendations will appear."));
  } else {
    const grid = el("div", { class: "card-grid" });
    recommendations.forEach((r) => {
      grid.append(el("div", { class: "rec-card", onClick: () => go(`#/tracks/${r.track_id}`) },
        el("div", { class: "rec-card__cover" }, "♪"),
        el("div", { class: "rec-card__title" }, r.title),
        el("div", { class: "rec-card__artist" }, r.artist)));
    });
    trackSection.append(grid);
  }
  wrap.append(trackSection);

  // ── Artist recommendations ────────────────────────────────────────────
  const artistSection = el("div", { class: "rec-section" });
  artistSection.append(el("p", { class: "rec-section__label" },
    "Artists · similar_to traversal · neo4j"));

  if (!artists.length) {
    artistSection.append(el("div", { class: "empty" },
      el("strong", {}, "No artist suggestions yet"),
      "Play some tracks to build up your listening history."));
  } else {
    const grid = el("div", { class: "artist-grid" });
    artists.forEach((a) => {
      const followBtn = el("button", { class: "btn btn--ghost btn--sm artist-card__follow" }, "Follow");

      // Check status, then wire toggle
      API.followStatus(a.artist_id).then(({ following }) => {
        followBtn.textContent = following ? "✓ Following" : "Follow";
        followBtn.classList.toggle("btn--active", following);
      });

      followBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        followBtn.disabled = true;
        try {
          const { following } = followBtn.classList.contains("btn--active")
            ? await API.unfollowArtist(a.artist_id)
            : await API.followArtist(a.artist_id);
          followBtn.textContent = following ? "✓ Following" : "Follow";
          followBtn.classList.toggle("btn--active", following);
          toast(following ? `Following ${a.name}` : `Unfollowed ${a.name}`);
        } catch (err) {
          toast(err.message, "error");
        } finally {
          followBtn.disabled = false;
        }
      });

      grid.append(
        el("div", { class: "artist-card", style: "cursor:pointer", onClick: (e) => { if (!e.target.closest("button")) openArtistModal(a.artist_id); } },
          el("div", { class: "artist-card__avatar" }, (a.name || "?")[0].toUpperCase()),
          el("div", { class: "artist-card__name" }, a.name),
          el("div", { class: "artist-card__meta" },
            `${a.track_count ?? 0} track${a.track_count === 1 ? "" : "s"}`),
          a.bio ? el("div", { class: "artist-card__bio" }, a.bio) : null,
          followBtn,
        )
      );
    });
    artistSection.append(grid);
  }
  wrap.append(artistSection);

  return wrap;
}
