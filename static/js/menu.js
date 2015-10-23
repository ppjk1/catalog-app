$(document).ready(function(){

    $('#login-link').hover(
        function() {
            $('.login-popup').fadeIn(250);
        }
    );

    $('.login-popup').mouseleave(
        function() {
            $(this).fadeOut(250);
        }
    );

    $('.menu-trigger').on('click', function(){
        $('#menu').toggle(400);
    });

});
