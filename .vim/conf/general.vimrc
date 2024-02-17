" $HOME/.vim/conf/general.vimrc

set nocompatible
filetype plugin on 	" Auto-detect un-labeled filetypes
syntax on 		      " Turn syntax highlighting on
set backspace=2     " Backspace behaves like other programs do
set hidden          " Undo persists even when switching to different open buffers

" searching
set hlsearch 		" When searching (/), highlights matches as you go
set incsearch 	" When searching (/), display results as you type (instead of only upon ENTER)
set smartcase 	" When searching (/), automatically switch to a case-sensitive search if you use any capital letters
set ignorecase  " be smart about case in search
set wildmenu    " visual autocomplete for command menu

" key maps
inoremap jk <Esc>
