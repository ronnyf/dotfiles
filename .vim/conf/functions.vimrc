" $HOME/.vim/conf/functions.vimrc

" Toggles the theme from light to dark
function! ToggleThemeMode(style)
    if a:style == "dark"
        set background=dark
        AirlineTheme tomorrow
        colorscheme Tomorrow-Night
    else
        set background=light
        colorscheme Tomorrow
        AirlineTheme tomorrow
    en
endfunction
