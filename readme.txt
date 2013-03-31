=== Juiz Last Tweet Widget ===
Contributors: CreativeJuiz
Donate link: https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=P39NJPCWVXGDY&lc=FR&item_name=Juiz%20Last%20Tweet%20Widget%20%2d%20WordPress%20Plugin&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHostedGuest
Tags: twitter, widget, social, sidebar, last, tweet, shortcode
Requires at least: 3.0.1
Tested up to: 3.4.2
Stable tag: 1.1.4

Add a widget to your sidebar to show your latest tweet(s) with style and without JavaScript! Retweet, Favorite and Reply links are available.

== Description ==

Add a widget to your sidebar to show your latest tweet(s) with style and without JavaScript! Retweet, Favorite and Reply links are available.

This sidebar's widget offer you the possibility to show your last tweet(s) (THE last by default) in your WordPress web site.
The advantage of this plugin is the absence of JavaScript script to load tweets from twitter : a very good point for your page speed.
Another advantage is the possibility to use a cache system with an adjustable period.
You also can show your avatar, action links (Favorite, Reply, Retweet), activate a slideshow of latest tweets, and customize the CSS.

**Features**

In admin:

* Easy to install.
* Panel for easy configuration (Appearance -> Widgets).
* Show or hide your avatar
* Default CSS can be disabled or customized
* Adjustable period for cache system
* Can active the action links
* Can active an auto slideshow script and chose delay between two tweets
* Shortcode to insert the widget where you want

In your site:

* Smart default style (CSS) and compatible with [Social Subscribers Counter](http://wordpress.org/extend/plugins/social-subscribers-counter/) styles
* Display link (with special CSS classes) for hastags, users, and web link (`nofollow` links)
* Display twitter's user link and statut's link
* Display source (web, Tweetdeck, etc.) when it's possible
* In option: Show action links like Retweet, Reply and Fav
* In option: little slideshow of one tweet in a list of tweets

For developpers, numerous hooks are available, template function is available (see FAQ for more info) ;)


**Languages**

* English
* German
* Spannish
* French
* Turkish (thanks to [Hakan](http://kazancexpert.com/ "His website")!)
* Nowegian (thanks to [Nilsel](http://wordpress.org/support/profile/nilsel "His WordPress profile")!)


–––––––––––––––––––––––
Français
–––––

Ajoute un widget à votre site pour lister vos derniers tweets, sans JavaScript ! Les liens Retweeter, Répondre et mettre en Favoris sont disponibles.

Ce widget de sidebar vous offre la possibilité d'afficher vos derniers tweets (LE dernier par défaut) dans votre site WordPress.
L'avantage de ce plugin est l'absence de JavaScript pour charger les tweets depuis Twitter : un très bon point pour la vitesse de vos pages.
Un autre avantage est la possibilie d'utiliser un système de cache avec une durée ajustable.
Vous pouvez également afficher votre avatar, des liens d'action (Répondre, Retweeter, Favoris), activer un slideshow des derniers tweets et personnaliser les CSS.

**Fonctionnalités**

Dans l'administration :

* Facile à installer.
* Panneau facile à configurer (Apparence -> Widgets).
* Affichez ou cachez votre avatar
* Styles par défaut personnalisable (peuvent être simplement désactivé ou écrasés)
* Durée du cache ajustable
* Possibilité d'activer les liens d'action
* Possibilité d'activer un diaporama et d'en choisir le delai entre deux tweets
* Shortcode disponible pour insérer le widget où vous le souhaitez

Dans votre site :

* Styles par défaut sobres et classes (CSS) et compatible avec les styles de [Social Subscribers Counter](http://wordpress.org/extend/plugins/social-subscribers-counter/)
* Affiche les liens (avec des classes spéciales) pour les hastags, utilisateurs, et liens classiques (liens en `nofollow`)
* Affiche un lien vers le statut et le compte twitter
* Affiche la source du tweet (web, Tweetdeck, etc.) quand c'est possible
* En option : affichage de liens d'action comme Retweeter, Répondre, Fav
* En option : mini diaporama composé d'un tweet dans votre liste des derniers tweets

Pour les développeurs, de nombreux hooks sont disponibles ainsi qu'une fonction de template (voir la FAQ pour plus d'info) ;)


**Langages**

* Anglais
* Allemand
* Espagnol
* Français
* Turc (merci à [Hakan](http://kazancexpert.com/ "Son site web") !)
* Norvégien (merci à [Nilsel](http://wordpress.org/support/profile/nilsel "Son profil WordPress")!)

== Installation ==

You can use one of the both method :

**Installation via your Wordpress website**

1. Go to the admin menu 'Plugins' -> 'Install' and search for 'Juiz last tweet'
1. Click 'install' and activate it
1. Configure your widget in Appearance -> Widgets

**Manual Installation**

1. Upload folder `juiz-last-tweet-widget` to the `/wp-content/plugins/` directory.
1. Activate the plugin through the 'Plugins' menu in WordPress.
1. Configure plugin in Appearance -> Widgets.

== Screenshots ==
1. Juiz Last Tweet in action (french interface)
2. Juiz Last Tweet in the admin (Widget view)
3. Juiz Last Tweet with avatar displayed and custom CSS
4. Juiz Last Tweet with avatar and action links displayed

== Frequently Asked Questions ==

Full documentation in the plugin folder ! (documentation.html)
Or here: [Documentation](http://creativejuiz.fr/blog/doc/juiz-last-tweet-widget-documentation.html)

= Why the widget show me an error of load for my tweets ? =

Try to visit the link : `http://search.twitter.com/search.rss?q=from%3AUSERNAME&rpp=4` by replacing "USERNAME" with your own username.
If nothing happens, try with : `http://api.twitter.com/1/statuses/user_timeline.rss?screen_name=USERNAME&count=4`
If nothing happens, it's the fault of Twitter API limitation.
If this link show your 2 last tweets, it's the fault of my script, so contact me.

Since the v1.1.3 of this plugin, this kind of error **should** only arrive the first time you activate it, if your Twitter flow is not accessible.

= Why the widget shows me less tweets than I ask it to show me ? =

Twitter do what it wants to do with its feeds of tweets. This plugin uses both of feeds and controls the two to know which is available. The first available is chosen. If the chosen feed don't have tweets enought (example: 2 tweets whereas you chose 4 tweets to display) the selected stream will not allow you to display all your tweets you want.

You can try to solve a part of the problem by switching two variables in my code (see `wp-content/plugins/juiz-last-tweet-widget/juiz-last-tweet.php`) on lines 400 and 401. You have $search_feed1 and $search_feed2.
Just change 1 by 2, and 2 by 1.

A future update will allow you to change the feed directly from widget interface (I hope).

= My tweets are not always updated =

Since the v1.1.3, the cache system prefers keep your old tweets instead of displaying a error message due to a lack of tweets inside the Twitter flow. It's a kind of security: old tweets are better than error message :)

= You need to custom the design, hide something ? =
You can use lot of CSS classes and filters to help you in you quest :)
See the documentation.html files inside your plugin folder !

= When I use my own CSS, defaults CSS seems to disappear ? =
Yeah, sorry, it's a bug. Please, update to 1.1.4 at least.


== Changelog ==

= 1.1.4 =
* New function jltw( $args )
* New function get_jltw ( $args );
* Markup fix (remove ID 'juiz_last_tweet_tweetlist', it's a class now)
* Conflict between your own CSS and default CSS fixed
* Fix for an error message in WP Debug Mode at the first use of the widget


= 1.1.3 =
* New widget option : action links (Reply, Retweet, Favorite)
* Better management of the cache system (try to preserve your tweets cached if Twitter clears its flow)
* New hooks for developer
* Optimization of hastag search link
* Fix for a Notice PHP error in WP Debug Mode
* Fix for shortcode (/!\ Use 0 and 1 instead of false and true now)

= 1.1.2 =
* New Twitter logo
* Hastag Regexp updated (better multilingual compatibility)
* Tested successfully on multiblog
* Files encoding fixes
* Some CSS improvement

= 1.1.1 =
* Little debug fix
* HTML fix (bad markup at the end of tweet)

= 1.1.0 =
* Correction in the date for PHP4 server
* Correction for cache system
* Add a shortcode (jltw)
* Add several hooks (see the FAQ or documentation.html file)
* Better control and switching of Twitter RSS feed
* Better links parser
* Some fixes with CSS (special case)
* Turkish translation by [Hakan](http://kazancexpert.com/ "His website")

= 1.0.4 =
* Optionnal autoslide tweets, one by one (use JavaScript)

= 1.0.3 =
* Bug fix for multiple Last Tweet Widgets
* Bug fix for HTML tag display inside Tweets

= 1.0.2 =
* Bug fix for cache system (now uses the WP cache ssystem)

= 1.0.1 =
* Bug fix for Twitter API limitation
* Bug fix for disabling default CSS
* You can now show your avatar

= 1.0.0 =
* Bug fix for initial cache
* Bug fix for empty pseudo

= 1.0.0 beta =
* Initial Release, beta.

== Informations ==

Another plugin :
* [Juiz Smart Mobile Admin](http://wordpress.org/extend/plugins/juiz-smart-mobile-admin/ "Your blog always with you")

You like it ? You can donate or [tweet](https://twitter.com/intent/tweet?hashtags=CreativeJuiz&original_referer=http%3A%2F%2Fwordpress.org%2Fextend%2Fplugins%2Fjuiz-last-tweet-widget%2F&related=geoffrey_crofte&source=WordPress&text=I%20use%20Juiz-Last-Tweet%20Plugin%20for%20WordPress.%20It's%20usefull!!&url=http%3A%2F%2Fwww.creativejuiz.fr%2Fblog%2Fwordpress%2Fwordpress-plugin-afficher-derniers-tweets-widget&via=geoffrey_crofte "Tweet a little word") for this plugin.
Thank you !
[Donate](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=P39NJPCWVXGDY&lc=FR&item_name=Juiz%20Last%20Tweet%20Widget%20%2d%20WordPress%20Plugin&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHostedGuest "Donate to this WordPress plugin")

Full documentation in the plugin folder ! (documentation.html)
Or here: [Documentation](http://creativejuiz.fr/blog/doc/juiz-last-tweet-widget-documentation.html)

== Upgrade Notice ==

= 1.1.1 =
Need an update if you downloaded 1.1.0

= 1.1.0 =
Lot of usefull things, and some fixes, update!! ;)

= 1.0.3 =
Upgrade if you want to display more than one widgets of this plugin

= 1.0.2 =
Upgrade if you tweets, tweets and tweets again and again

= 1.0.1 =
Need upgrade

= 1.0.0 =
No need to upgrade if your tweets are displayed.

= 1.0.0 beta =
New version in test...
