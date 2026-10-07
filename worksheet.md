# Git Worksheet

_Git Workshop -- Tech GC -- October 10, 2026_

## _Activity Overview_

**Activity Name**: GC Racing Game, built by configuration

**Objective**: Learn Git branch management, merging, and conflict resolution by turning one boring game into a playable one, together.

**Group Size**: 2-4 people per group

**Team Roles Reference**: Driver, Track Engineer, Scenery Artist, Traffic Controller

**The one rule**: you only ever edit `config.js`.

---

## _Exercises_

### **Exercise 0 : Environment Setup**

_SSH Setup_: Refer to [ssh_setup.pdf](ssh_setup.pdf)

_Set your identity_: commits carry whichever name and address are configured here.

```
git config
```

### **Exercise 1 : Remote to Local**

> _Get your group's repository._

- **Connect to the remote repository and clone it.** Recommended Commands:

```
git config
git clone
```

- **Open the game.** Double-click `index.html`. Click the title card, drive with the arrow keys. It should be a straight road, an empty roadside, and nobody else on it.

```{=latex}
\newpage
```

### **Exercise 2 : Modification I**

> _Put your name on the title card._

- **Add your name to `team.authors` in `config.js`, then change and commit.** Recommended Commands:

```
git status
git add
git diff
git commit
```

- **Look at what you just did.** `git diff HEAD~1` shows your commit as a diff, `git show` shows it with the message.

### **Exercise 3 : Branch & Modification II**

> _Tune your part of the game._

- **Undo your commit and save your changes to the staging area.** Recommended Command:

```
git reset --soft HEAD~1
```

- **Create and switch to a branch named after your role.** Recommended Commands:

```
git branch
git checkout
```

- **Change your part of `config.js` and commit again.** Reload the browser after each change - that is the feedback loop. The Driver owns `player` and `physics`, the Track Engineer owns `track`, the Scenery Artist owns `background`, `scenery` and `colors`, the Traffic Controller owns `rivals`, `fog` and `difficulty`.

### **Exercise 4 : Merge & Conflict**

> _Manually edit to resolve conflicts._\
> _Merge every role's work into one working game._

- **Push changes to the remote repository.** Recommended Command:

```
git push
```

- **Merge the branches and resolve conflict.** Recommended Commands:

```
git merge
git rebase
```

- **Tag the result.** Recommended Command:

```
git tag
```

```{=latex}
\newpage
```

### _Final Result Example_

The deliverable is the merged `config.js`:

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

Note: This is merely an example. Reload `index.html` and the road bends, the trees are back, there is traffic to avoid, and your names are on the title card. The settings are yours to argue about — we can't wait to see what your group builds.

---

## _Activity Checklist_

### Preparation Phase

- [ ] Git environment configuration completed
- [ ] Repository cloned, game running
- [ ] Baseline confirmed boring
- [ ] Role assignment clarified

### Execution Phase

- [ ] Acquisition of basic Git commands
- [ ] All branches created successfully
- [ ] Individual tuning by each role completed
- [ ] Merge conflict experience completed
- [ ] Conflict resolution discussion conducted
- [ ] Game still runs after every merge
- [ ] Final integration successful

### Conclusion Phase

- [ ] Every group member's name on the title card
- [ ] `v1.0` tagged
- [ ] Work showcase and sharing
- [ ] Git techniques review

---

_Now that you have mastered the core workflow of Git, keep exploring and make it a powerful assistant in your collaborative projects!_
