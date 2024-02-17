" $HOME/.vim/conf/themes.vimrc

set guifont=Source\ Code\ Pro:h15 " Set SourceCodePro as the default font with a size of 15.
if has("gui_running")
    set guioptions-=T  " Make the toolbar stay hidden after a restart.
endif

" themes
try 
    colorscheme wwdc16
    set background=dark
    set termguicolors
catch
    colorscheme gruvbox
    set background=dark
    set termguicolors
endtry

