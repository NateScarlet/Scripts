cmd /c setup_gitproxy.cmd
git config --global core.editor "code.cmd --wait --reuse"
git config --global core.autocrlf input
git config --global alias.amend "commit --amend --no-edit"
