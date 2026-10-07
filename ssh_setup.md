# SSH Setup for FOCS Gitea

## Step one

Run the following command to check if you have generated an ssh key before.

```sh
ls ~/.ssh | grep id_ed25519
```

If nothing shows up, that means you haven't generated ssh keys before and you can safely follow the rest of the steps. In rare cases where something does show up, you should jump to step three.

## Step two

Generate the SSH key with the following command:

```sh
ssh-keygen -t ed25519 -C "<jAccount>@sjtu.edu.cn"
```

Replace `<jAccount>` with your actual jAccount. Press enter key until prompts end.

## Step three

Print your public key with the following command:

```sh
cat ~/.ssh/id_ed25519.pub
```

Copy the content of the output and navigate to [User settings for SSH/GPG Keys](https://focs.ji.sjtu.edu.cn/git/user/settings/keys). Click "Add Key" and fill in "Key Name" and "Content":

- Key Name: Anything you like.

- Content: The content you just copied.

## Step four

Verify you have successfully set up SSH key for FOCS Gitea.

```sh
ssh -p 2222 git@focs.ji.sjtu.edu.cn
```

If you get the following output, you have successfully set up SSH key for FOCS Gitea.

```text
PTY allocation request failed on channel 0
Hi there, <jAccount>! You've successfully authenticated with the
key named <Key Name>, but Gitea does not provide shell access.
If this is unexpected, please log in with password and setup
Gitea under another user.
Connection to focs.ji.sjtu.edu.cn closed.
```

Now, whenever you clone a FOCS repository or add a FOCS repository to remote, you should specify the url as \nolinkurl{ssh://git@focs.ji.sjtu.edu.cn:2222/PATH/TO/REPO} and replace `PATH/TO/REPO` with the actual path to the repository. For example,

```sh
git clone ssh://git@focs.ji.sjtu.edu.cn:2222/engr101s1/<repo>
```

or

```sh
git remote add origin \
ssh://git@focs.ji.sjtu.edu.cn:2222/engr101s1/<repo>
```

Note: the web url of a focs repository has a different path from the ssh url, namely `/git/engr101s1/<repo>` for web and `/engr101s1/<repo>` for ssh. The latter is the correct path while using git.

Tip: on the webpage of the repository, you can click the "stacked squares" button on the right of the `ssh://` url to copy the usable repo url for your `git clone` command.

Congratulations! If you're only trying to set up SSH key for FOCS Gitea, you may now close this document. The following material is advanced and NOT required reading.

## Advanced SSH setup

### SSH config file

SSH config file contains advanced configuration for SSH. It is located at `~/.ssh/config`. The configuration for FOCS Gitea may be specified in the config file like the following:

```ssh-config
# FOCS Gitea
Host focs
 Hostname focs.ji.sjtu.edu.cn
 User git
 IdentityFile ~/.ssh/id_ed25519
 IdentityOnly yes
 AddKeysToAgent yes
 Port 2222
```

Correspondingly, when cloning or adding remote, you can now specify the url as `focs:/PATH/TO/REPO`.

### Generic SSH setup for remote Git services

The procedure for other remote Git services is very similar to that for FOCS Gitea. Here are the differences:

- Replace SJTU email with the appropriate email address for your repository.

- Change the port accordingly. The default port is 22.

- Change the key accordingly. Details are discussed in the next section.

### Multiple SSH keys

In general, it's a good idea to use different keys for different remote Git services. To create more than one keys, enter `~/.ssh/NAME` when prompted for which file to save it and replace `NAME` accordingly. Modify the `IdentityFile` line in your SSH config file too.
