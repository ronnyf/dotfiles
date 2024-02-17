" $HOME/.vim/conf/leader.vimrc

let mapleader=","       " set the leader key to the comma key
nnoremap <leader>h :noh<CR> " toggle search highlighting
map <leader>vd :call ToggleThemeMode('dark')<CR>
map <leader>va :call ToggleThemeMode('')<CR>
