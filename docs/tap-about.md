# About The Accountability Project

*"While headlines flood, the record stands."*

The Accountability Project consolidates the daily flood of headlines into cohesive, topic-based, and verifiable records of documented government actions. Nothing publishes until it clears code-enforced checks: sourcing standards, duplicate detection, and per-entry evidence requirements.

## How this started

TAP began in early 2025 as a personal reference archive of news reports about changes happening in the federal government. The daily flood of coverage made it hard to keep track of what actually mattered, and a lot of it was getting lost in the churn of the news cycle. As the volume kept growing, I started using AI-based tools to help manage the archive — and over the following months the project evolved from a simple collection of clippings into a system built to maintain a verifiable accounting of government activity, with a strong focus on who did what.

TAP finds, retrieves, and evaluates information about government activity using automated, code-enforced accuracy and sourcing checks, then folds the results into ongoing narratives — so a reader gets the big picture of an unfolding story, not just whatever headline ran that day. Right now the system focuses on three areas: corporate deregulation, accountability-relevant conduct by high-ranking officials, and the redirection of government services. Those topics can change without changing the underlying tooling.

## How accuracy is built in

**Raw reporting gets filtered and deduplicated before it becomes an entry.**
A single policy announcement can spawn dozens of overlapping news stories
across days or weeks; those get clustered into one event and checked for
specifics — a named official, a cited statute, a quantified impact — before
anything is written up, rather than being treated as dozens of separate,
thinner stories.

**Primary sources come first, wherever they exist.** Each of the three
curated trackers ranks its sourcing differently based on what's actually
available for that subject matter — Corporate Deregulation and
Cabinet-Level Accountability lean most heavily on agency filings, court
dockets, Federal Register entries, and GAO or Inspector General findings;
Government Service Redirection leans more on investigative and mainstream
reporting, since primary documentation is often thinner for that kind of
change. In every case, the strongest available source type is used first,
and the entry says which kind of source it's relying on.

**Entries are framed to a legal standard, not a political one — and lawful
conduct is never inflated into something it isn't.** In the Cabinet-Level
Accountability tracker, entries alleging an actual statutory or
constitutional violation lay out the legal elements that would need to be
proven, then map specific evidence to each element. Entries about conduct
that's lawful but still accountability-relevant — a pardon, a personnel
removal, an appointment — are labeled as an accountability concern instead,
never dressed up as an alleged violation. Alleged conduct and proven conduct
are always kept distinct — an open investigation is never presented as a
settled finding.

**Facts and modeled estimates are kept strictly separate.** Verifiable
government actions — a signed directive, an administrative stay, a formal
notice of proposed rulemaking — are documented on their own. Any modeled
figure layered on top, like an estimated cost, job loss, or health impact,
has to cite the specific agency analysis or academic source that produced
it, so a reader can tell a documented fact from a projection.

**Every entry carries a confidence note.** This is a plain-language flag
for how strongly an entry should be relied on — whether the sourcing is
solid, contested, or still developing. A user can see at a glance whether
they're looking at something well-established or something with
acknowledged limits.

**Individuals are named, not vague institutions.** Whether it's a Cabinet
official facing statutory liability or an agency administrator driving a
regulatory rollback, an entry says which specific official did what,
wherever it can be documented, rather than attributing an action to "the
administration" generically.

**Genuine disputes get fair treatment.** If a fact or characterization is
actually contested, the entry says so and presents the other side's
rationale — it doesn't quietly pick a side.

**Nothing publishes without clearing code-enforced gates, and entries get
rechecked, not just written once.** Every entry has to pass validation
scripts that check far more than syntax — required evidence, sourcing, and
confidence caveats all have to be present before a build can succeed. After
publishing, each of the three curated trackers also has an automated
staleness check that flags entries whose underlying status may have changed
(ongoing litigation, a "proposed" action that may since have been
finalized, or an entry that simply hasn't been reverified in over 60 days).
Flagged entries are worked through in batches, and corrections get made
when something's found to be out of date — this has already caught and
fixed real errors, like an entry about active litigation that had actually
been dismissed months earlier.

## How information gets presented

Five trackers, organized by kind of action, not by target — each one built to answer a different question, and sourced differently to match.

| Tracker | What it covers |
|---|---|
| Corporate Deregulation | What public health, environmental, labor, or financial rule was rolled back, which interests lobbied for it, and what the estimated impact is |
| Cabinet-Level Accountability | Documented prosecution exposure and other accountability-relevant conduct for current officials — legal allegations framed to legal standards, non-legal conduct labeled as such |
| Government Service Redirection | What government capacity was suppressed, defunded, or reassigned, and what oversight bodies or courts found |
| Reporting | A running archive of relevant news coverage — broader in scope, sourced to established news organizations by design |
| User Topics | Reader-suggested topics that don't clear the bar for one of the three curated trackers, given a verdict rather than a quantified impact figure — see below |

The three curated trackers — Corporate Deregulation, Cabinet-Level
Accountability, and Government Service Redirection — are built the same
way: a plain-language summary of what happened, a short summary of each key
section composed specifically for that entry (not an automated truncation
of the longer text), a confidence note, and a list of sources with links
back to the original material. Reporting works differently by design: it's
an automated archive of gathered news coverage, so each entry carries a
plain description of what happened and why it matters, plus a source link
on over 99% of entries.

## User Topics

Readers can suggest a topic, story, or government action through the
site's Suggest a Topic button. Anything real that doesn't clear the bar
for one of the three curated trackers — usually because it's broader
than a single named action, or because research doesn't turn up a
named official, a specific violation, and independent sourcing — still
gets a real, researched entry here rather than being turned away.

Each entry gets a plain-language summary and real sources, then a
verdict: Confirmed, Partially Confirmed, Unable to Verify, or
Misleading as Stated. That's a lighter research standard than the
curated trackers' — it doesn't map evidence to legal elements — but
it's still genuine research, not a rubber stamp. A topic that later
turns out to clear a curated tracker's bar gets promoted there, with a
note left behind showing where it started.

Search or browse. Search by keyword, statement, or topic across
everything, or browse tracker by tracker to stay within one kind of
action.
