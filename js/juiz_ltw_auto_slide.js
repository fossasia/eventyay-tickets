jQuery(document).ready(function(){

	if( jQuery('.juiz_ltw_autoslide').length > 0 ) {
	
		jQuery('.juiz_ltw_autoslide').each(function(){
		
			var $parent = jQuery(this);
			var $tweets = $parent.find('li');
			var ltw_the_delay = $parent.data('delay');
			var ltw_interval;
			
			if ( $tweets.length > 1 ) {
				jQuery($tweets).filter(':not(":first")').hide();
				jQuery($tweets).filter(':first').addClass('current');
				
				jQuery($parent).addClass('hasjs');
				$parent.prepend($parent.find('.user_avatar'));
				$parent.find('ul .user_avatar').remove();
				
				
				function juiz_ltw_next_one() {
					
					if( jQuery($parent).find('.current').next('li').length > 0 ) {
						jQuery($parent).find('.current').hide().removeClass('current').next('li').fadeIn(400).addClass('current');
					}
					else {
						jQuery($parent).find('.current').hide().removeClass('current');
						jQuery($tweets).filter(':first').addClass('current').fadeIn(400);
					}
						
				}
				
				ltw_interval = setInterval(juiz_ltw_next_one, ltw_the_delay*1000);
				
				$tweets.mouseenter(function(){
					clearInterval(ltw_interval);
					ltw_interval = false;
				})
				.mouseleave(function(){
					if(!ltw_interval)
						ltw_interval = setInterval(juiz_ltw_next_one, ltw_the_delay*1000);
				});
			}
			
		});
		
	}

});