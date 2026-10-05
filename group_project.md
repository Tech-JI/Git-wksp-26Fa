# GC Racing Game - Git Collaboration Workshop Activity Plan

## Activity Overview

**Activity Name**: GC Racing Game, built by configuration
**Objective**: Learn Git branch management, merge conflict resolution and team collaboration by turning one deliberately boring game into a playable one
**Duration**: 1.5 hours for the core phases, about 3 hours for all ten exercises
**Group Size**: 3-4 people per group

You are not being asked to write a game. You are being asked to *change* one, as a team, on branches, in a way that survives being merged.

The starting point is a car on a straight empty road. Nothing to look at, nobody else on it. Everything about it - the road, the scenery, the traffic, the colours, the weather, how the car handles - lives in a single file, and each of you will own a different part of that file. Then you merge each other's work, and some of those merges will conflict, on purpose. Resolving them well is the skill this project is actually about.

## Activity Preparation

### Environment Setup

```bash
# 1. Set your identity - commits carry whoever is configured here
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

```bash
# 2. Get your group's repository
git clone [repository-url] racer
cd racer
```

Then open `index.html` in a browser - double-click it. There is nothing to install and nothing to build. Click the title card, and drive with the arrow keys or W A S D.

> If you want to make debugging easier, you can try `python3 -m http.server 8000` and open `http://localhost:8000/` instead: over HTTP the browser names the exact line when `config.js` fails to parse, which on a `file://` page it refuses to do.

### The file you all edit

**One rule matters more than the rest: you only ever edit `config.js`.** That is the whole project. The game reads nothing else from you.

```js
window.RACER_CONFIG = {

  team: {
    title:      'GC Racing Game',
    authors:    [ 'GitWksp26Fa Group Project' ],   // everyone appends here
    intensity:  1.0,                               // one multiplier, everyone argues about it
  },

  player:    { hue: 0, saturate: 1.0, brightness: 1.0, maxOffRoad: 3 },

  track:     { preset: 'blank',                    // 'blank' = one long straight road
               sections: [ /* the track, one line per section */ ],
               roadWidth: 2000, lanes: 3 },

  scenery:   { density: 0.0,                       // 0 = empty roadside
               palms: 1.0, columns: 1.0, plants: 1.0, billboards: 1.0 },

  rivals:    { count: 0,                           // 0 = nobody else on the road
               speedMin: 0.25, speedMax: 0.75 },

  physics:   { maxSpeedScale: 1.0, accel: 0.2, centrifugal: 0.3 },

  fog:       { density: 0 },

  // ...and difficulty, viewport, colors, background, camera, sprites, hud, audio
};
```

The shipped values are the boring baseline: a straight road, an empty roadside, no traffic, no fog. Every change a group makes is visibly an improvement, which is the point.

If you break a setting, the game keeps running and puts a red box in the corner telling you which line is wrong. If you break the whole file - a missing comma, a leftover merge conflict marker - the page says so instead of going blank. You cannot brick this permanently; that is deliberate, because a group of people editing one file needs mistakes to be legible.

### Team Roles Reference

- **Driver** - owns `player` and `physics`. The car: its colour, its top speed, how it drifts through corners.
- **Track Engineer** - owns `track`. The road: straights, curves, hills, S-bends, width, lanes.
- **Scenery Artist** - owns `background`, `scenery` and `colors`. The world: sky, parallax layers, roadside trees, the whole palette.
- **Traffic Controller** - owns `rivals`, `fog` and `difficulty`. The other cars, the weather, how hard it is.

### The three arguments you are going to have

They are not accidents. Each is a different shape of conflict, from easy to real.

1. **`team.authors`** - everybody appends their own name to the same list. Trivial to resolve, and it teaches you what the markers mean. It also pays off: the names print on the title card.
2. **`team.intensity`** - one multiplier over scenery density, rival count *and* top speed. The Scenery Artist wants it higher to fill the world, the Traffic Controller wants it lower so the track is survivable, the Driver wants it higher because speed is fun. You cannot all be right. Decide together, then write down one number.
3. **`track.sections`** - two people adding sections to the same list. Small, adjacent conflicts: the most common shape you will meet in real work.

## Detailed Activity Process

### Phase 1: Project Launch (15 minutes)

#### 1.1 Project Introduction

```bash
# Make sure the game runs before you touch anything
git clone [repository-url] racer
cd racer
git log --oneline
```

Open `index.html`. Confirm it is boring: a straight road, nothing beside it, nobody else on it. If it looks broken you will spend the rest of the session assuming *you* broke it, so settle that first.

#### 1.2 Branch Strategy Explanation

```bash
# Each role takes its own branch, named after what it owns
git switch -c feature/drive-feel     # Driver
git switch -c feature/track          # Track Engineer
git switch -c feature/scenery        # Scenery Artist
git switch -c feature/traffic        # Traffic Controller
```

### Phase 2: Independent Tuning (30 minutes)

#### 2.1 Individual Work by Role

Work only inside the part of `config.js` you own. Reload the browser after each change - that is the feedback loop, and it takes a second.

**Driver example:**

```bash
git switch feature/drive-feel
```

```js
player: {
  hue:                   240,      // the car goes blue
  maxOffRoad:            3,
},
physics: {
  maxSpeedScale:         1.0,
  centrifugal:           0.3,      // try 0 once: corners stop pushing you sideways at all
  steerRate:             2.0,
},
```

**Track Engineer example:**

```bash
git switch feature/track
```

```js
track: {
  preset:                'sections',   // stop being a straight line
  sections: [
    { type: 'straight',     length: 25  },
    { type: 'curve',        length: 50,  curve: 4,  hill: 20 },
    { type: 'sCurves',      scale: 1 },
    { type: 'hill',         length: 100, hill: 60 },
  ],
  lanes:                 3,
},
```

**Scenery Artist example:**

```bash
git switch feature/scenery
```

```js
scenery: {
  density:               2.0,      // 0 empty, 1 normal, 2 twice as busy
},
background: {
  layers: [
    { slice: 'SKY',     speed: 0.001 },
    { slice: 'HILLS',   speed: 0.002 },
    { slice: 'TREES',   speed: 0.003 },
  ],
},
colors: {
  sky:                   '#72D7EE',
  fog:                   '#72D7EE',   // equal to sky = a clean horizon
},
```

**Traffic Controller example:**

```bash
git switch feature/traffic
```

```js
rivals: {
  count:                 40,
  speedMin:              0.25,
  speedMax:              0.75,
},
fog: {
  density:               5,        // 0 clear, 5 the original haze, 30 you cannot see the next corner
},
```

#### 2.2 Commit Standards

Commit messages follow `type(scope): what changed`, where the types are `feat`, `fix`, `docs`, `style`, `refactor`, `test` and `chore`, and the scope is the part of `config.js` you touched.

```bash
git status                       # what have I touched?
git diff                         # what exactly did I change?
git add config.js
git commit -m "feat(scenery): thicken the roadside and uncomment the sky layers"
```

Six months from now, `git log --oneline` is the only documentation that will still be true.

### Phase 3: Merge Conflict Experience (25 minutes)

#### 3.1 First Merge Attempt

```bash
# Switch back to the main branch
git switch master

# Try merging the scenery work
git merge feature/scenery
```

If nobody has touched `master` since you branched, that is a **fast-forward**: no merge commit, the branch label just moves. To see the other kind, make a small change on `master` first and merge again - now git has two lines of history and has to build a merge commit.

```bash
git merge feature/track     # conflict will occur here if two of you touched the same lines
```

```bash
# See the shape of the history you just made
git log --graph --oneline --all --decorate
```

#### 3.2 Typical Conflict Scenarios

**The shared multiplier - both roles want the same line:**

```
<<<<<<< HEAD
    intensity:             1.0,
=======
    intensity:             2.0,
>>>>>>> feature/scenery
```

**Two names on the same list:**

```
    authors: [
      'GitWksp26Fa Group Project',
<<<<<<< HEAD
      'AAA',
=======
      'BBB',
>>>>>>> feature/traffic
    ],
```

**Two sections in the same list:**

```
    sections: [
      { type: 'straight',     length: 25  },
<<<<<<< HEAD
      { type: 'curve',        length: 50,  curve: 4 },
=======
      { type: 'sCurves',      scale: 1 },
>>>>>>> feature/track
    ],
```

### Phase 4: Conflict Resolution Workshop (20 minutes)

#### 4.1 Conflict Resolution Strategies

1. `git status` to see which files are unmerged.
2. Open the file and find the markers.
3. Decide what the game should do - not who wins.
4. Delete `<<<<<<<`, `=======` and `>>>>>>>`, and leave exactly what you decided.
5. `git add config.js`, then `git commit`.
6. Reload the page. Does it still run?

```bash
git add config.js
git commit -m "fix: resolve the intensity conflict, settle on 1.5"
```

#### 4.2 Team Collaboration Tools

```bash
# Compare two people's work before merging either
git diff feature/scenery feature/track

# See the whole history, including the branches you have not merged yet
git log --oneline --graph --all
```

There is no trick to any of this. Read both sides, decide together, delete the markers, keep the result working. What you are practising is the conversation, not the keystrokes.

### Phase 5: Final Integration and Presentation (15 minutes)

#### 5.1 Complete Merge

```bash
# Merge what is left
git merge feature/drive-feel

# Push the result
git push origin master

# Mark the release
git tag v1.0 -m "group build"
```

Everyone should also push their own branch - not just the merged result - so the group can review each other's work:

```bash
git push -u origin feature/scenery
```

#### 5.2 Work Showcase

The finished `config.js` is the deliverable:

```js
window.RACER_CONFIG = {
  team: {
    title:      'GC Racing Game',
    authors:    [ 'GitWksp26Fa Group Project', 'AAA', 'BBB', 'CCC', 'DDD' ],
    intensity:  1.5,
  },
  player:    { hue: 240, saturate: 1.2 },
  track:     { preset: 'sections', lanes: 4 },
  scenery:   { density: 2.0 },
  rivals:    { count: 40 },
  fog:       { density: 5 },
  // ...
};
```

Reload `index.html`: your names are on the title card, the road bends, the trees are back, and there is traffic to avoid. Then look at the graph you just made:

```bash
git log --graph --oneline --all --decorate
```

Every branch, every merge, every conflict you resolved is in that picture.

## Activity Checklist

### Preparation Phase

- [ ] Git username and email configured
- [ ] Repository cloned, game runs, baseline confirmed boring
- [ ] Roles assigned, one branch per person
- [ ] `README.md` and `docs/WORKSHOP.md` open

### Execution Phase

- [ ] All branches created successfully
- [ ] Each role's part of `config.js` changed and committed
- [ ] Branches merged into `master`
- [ ] Merge conflict experience completed
- [ ] Conflict resolution discussion conducted
- [ ] Game still runs after every merge
- [ ] Final integration successful

### Conclusion Phase

- [ ] Every group member's name on the title card
- [ ] `v1.0` tagged
- [ ] Work showcase and sharing
- [ ] Git techniques review
- [ ] Branches pushed and reviewed

## Teaching Points

### Git Skills Focus

1. Branch management: create, switch, list, delete branches
2. Merge strategies: fast-forward merge, three-way merge
3. Conflict resolution: manual editing, tool usage, committing the result
4. Undo: `git restore`, `git reset --soft/--mixed/--hard`, `git stash`
5. History as a tool: `git log --graph`, `git blame`, `git bisect`

### Collaboration Skills Focus

1. Communication and coordination: agreeing on the shared number *before* you both change it
2. Problem solving: a conflict is a design decision someone has to make
3. Quality assurance: every setting has a unit and a range; out of range is a defect, not a style opinion, and the game will say so
