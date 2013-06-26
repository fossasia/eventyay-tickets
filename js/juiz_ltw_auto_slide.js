jQuery(document).ready(function($){

	if( $('.juiz_ltw_autoslide').length > 0 ) {
	
		$('.juiz_ltw_autoslide').each(function(){
		
			var $parent = $(this);
			var $tweets = $parent.find('li');
			var ltw_the_delay = $parent.data('delay');
			var ltw_interval;
			
			if ( $tweets.length > 1 ) {
				$($tweets).filter(':not(":first")').hide();
				$($tweets).filter(':first').addClass('jltw_current');
				
				$($parent).addClass('hasjs');
				$parent.prepend($parent.find('.user_avatar'));
				$parent.find('ul .user_avatar').remove();
				
				
				function juiz_ltw_next_one() {

					$current_one = $($parent).find('.jltw_current');

					if( $current_one.next('li').length > 0 ) {
						$current_one.hide().removeClass('jltw_current').next('li').fadeIn(400).addClass('jltw_current');
					}
					else {
						$current_one.hide().removeClass('jltw_current');
						$($tweets).filter(':first').addClass('jltw_current').fadeIn(400);
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