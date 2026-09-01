<?php
/**
 * Plugin Name: Snackspert Review API
 * Description: Eigen REST-endpoint om dagelijks een nieuwe zaakjes-review direct live te publiceren als "restaurant"-item, inclusief ACF-velden, hoofdfoto en koppeling naar een locatie.
 * Version:     1.0.0
 * Author:      Snackspert
 * License:     GPL-2.0-or-later
 *
 * Installeren: dit bestand uploaden naar wp-content/mu-plugins/ (map desnoods zelf
 * aanmaken). Mu-plugins zijn altijd actief en kunnen niet per ongeluk uitgezet worden.
 *
 * Waarom een eigen endpoint en niet de standaard /wp/v2/restaurant route:
 * de ACF-veldgroep "Restaurant settings" staat op show_in_rest = 0, en drie velden
 * hebben een schrijfvorm die je van buitenaf makkelijk fout doet (image wil een
 * attachment-ID, location wil een bestaand post-ID, map wil een array). Dit endpoint
 * schrijft die velden server-side met update_field(), dus show_in_rest hoeft
 * daarvoor niet aan te staan.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! class_exists( 'Snackspert_Review_API' ) ) :

class Snackspert_Review_API {

	const REST_NS     = 'snackspert/v1';
	const POST_TYPE   = 'restaurant';
	const LOC_TYPE    = 'locatie';
	const GROUP_KEY   = 'group_6648e5673b80c';
	const MAX_IMAGE   = 12582912; // 12 MB, ruim genoeg voor een telefoonfoto.

	/** @var array<string,array>|null Cache van veldnaam => ACF-velddefinitie. */
	private $fields = null;

	public static function boot() {
		$self = new self();
		add_action( 'rest_api_init', array( $self, 'register_routes' ) );
	}

	public function register_routes() {
		register_rest_route(
			self::REST_NS,
			'/reviews',
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'create_review' ),
				'permission_callback' => array( $this, 'can_publish' ),
			)
		);

		register_rest_route(
			self::REST_NS,
			'/schema',
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'get_schema' ),
				'permission_callback' => array( $this, 'can_publish' ),
			)
		);

		register_rest_route(
			self::REST_NS,
			'/locaties',
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'get_locaties' ),
				'permission_callback' => array( $this, 'can_publish' ),
			)
		);
	}

	/**
	 * Publiceren mag alleen met een account dat het ook in wp-admin zou mogen.
	 * Application Passwords leveren hier een gewone ingelogde gebruiker aan.
	 */
	public function can_publish() {
		if ( ! is_user_logged_in() ) {
			return new WP_Error( 'snackspert_geen_auth', 'Geen geldige authenticatie meegestuurd.', array( 'status' => 401 ) );
		}
		if ( ! current_user_can( 'publish_posts' ) ) {
			return new WP_Error( 'snackspert_geen_rechten', 'Dit account mag geen berichten publiceren.', array( 'status' => 403 ) );
		}
		return true;
	}

	/* ---------------------------------------------------------------- ACF */

	/** ACF actief? */
	private function acf_ready() {
		return function_exists( 'acf_get_field_group' ) && function_exists( 'update_field' );
	}

	/**
	 * Veldnaam => velddefinitie voor de veldgroep. We schrijven altijd op field
	 * key (field_xxx) en niet op naam: dat is de enige vorm waarvan ACF de
	 * key-referentie (_veldnaam meta) gegarandeerd goed wegschrijft, en zonder die
	 * referentie toont de front-end het veld niet.
	 */
	private function fields() {
		if ( null !== $this->fields ) {
			return $this->fields;
		}
		$this->fields = array();
		if ( ! $this->acf_ready() ) {
			return $this->fields;
		}
		$group = acf_get_field_group( self::GROUP_KEY );
		if ( ! $group ) {
			return $this->fields;
		}
		foreach ( (array) acf_get_fields( $group ) as $field ) {
			if ( ! empty( $field['name'] ) ) {
				$this->fields[ $field['name'] ] = $field;
			}
		}
		return $this->fields;
	}

	private function field( $name ) {
		$fields = $this->fields();
		return isset( $fields[ $name ] ) ? $fields[ $name ] : null;
	}

	/** Toegestane waardes van een select-veld, rechtstreeks uit ACF. */
	private function choices( $name ) {
		$field = $this->field( $name );
		if ( ! $field || empty( $field['choices'] ) || ! is_array( $field['choices'] ) ) {
			return array();
		}
		return array_map( 'strval', array_keys( $field['choices'] ) );
	}

	/**
	 * Waardes tegen de ACF-keuzelijst leggen. Vergelijking is hoofdletter- en
	 * accentongevoelig, zodat "Kroket" en "kroket" allebei werken, maar wat we
	 * wegschrijven is altijd exact de waarde zoals ACF hem kent.
	 */
	private function match_choices( $waardes, $veld, &$fouten ) {
		$toegestaan = $this->choices( $veld );
		$resultaat  = array();

		foreach ( (array) $waardes as $waarde ) {
			$waarde = trim( (string) $waarde );
			if ( '' === $waarde ) {
				continue;
			}
			if ( ! $toegestaan ) {
				$resultaat[] = $waarde; // Geen keuzelijst bekend: niets te toetsen.
				continue;
			}
			$gevonden = null;
			foreach ( $toegestaan as $optie ) {
				if ( 0 === strcasecmp( $optie, $waarde ) ) {
					$gevonden = $optie;
					break;
				}
			}
			if ( null === $gevonden ) {
				$fouten[] = sprintf(
					'"%s" is geen geldige waarde voor %s. Kies uit: %s.',
					$waarde,
					$veld,
					implode( ', ', $toegestaan )
				);
				continue;
			}
			if ( ! in_array( $gevonden, $resultaat, true ) ) {
				$resultaat[] = $gevonden;
			}
		}

		return $resultaat;
	}

	/* ------------------------------------------------------------ endpoint */

	public function create_review( WP_REST_Request $request ) {
		if ( ! $this->acf_ready() ) {
			return new WP_Error( 'snackspert_geen_acf', 'ACF is niet actief op deze site; de reviewvelden kunnen niet geschreven worden.', array( 'status' => 501 ) );
		}
		if ( ! $this->fields() ) {
			return new WP_Error(
				'snackspert_geen_veldgroep',
				sprintf( 'Veldgroep %s niet gevonden. Is de key gewijzigd?', self::GROUP_KEY ),
				array( 'status' => 501 )
			);
		}

		$body = $request->get_json_params();
		if ( ! is_array( $body ) ) {
			$body = $request->get_params();
		}

		$fouten        = array();
		$waarschuwingen = array();

		$naam = isset( $body['naam'] ) ? sanitize_text_field( wp_unslash( $body['naam'] ) ) : '';
		if ( '' === $naam ) {
			$fouten[] = 'Veld "naam" (de zaaknaam, wordt de posttitel) ontbreekt.';
		}

		$tekst = isset( $body['tekst'] ) ? (string) $body['tekst'] : '';
		if ( '' === trim( wp_strip_all_tags( $tekst ) ) ) {
			$fouten[] = 'Veld "tekst" (de reviewtekst) is leeg.';
		}
		if ( 'plat' === ( isset( $body['tekst_formaat'] ) ? $body['tekst_formaat'] : 'html' ) ) {
			$tekst = wpautop( $tekst );
		}
		$tekst = wp_kses_post( $tekst );

		$categorie      = $this->match_choices( isset( $body['category'] ) ? $body['category'] : array(), 'category', $fouten );
		$hoofdcategorie = $this->match_choices( isset( $body['main_category'] ) ? $body['main_category'] : array(), 'main_category', $fouten );
		$dieet          = $this->match_choices( isset( $body['diet'] ) ? $body['diet'] : array(), 'diet', $fouten );

		if ( count( $hoofdcategorie ) > 1 ) {
			$fouten[] = 'main_category is een enkelvoudig veld; geef er precies een op.';
		}
		if ( ! $hoofdcategorie ) {
			$waarschuwingen[] = 'Geen main_category opgegeven: de detailpagina kan dan geen gerelateerde restaurants tonen.';
		}

		if ( $fouten ) {
			return new WP_Error(
				'snackspert_ongeldige_invoer',
				implode( ' ', $fouten ),
				array(
					'status' => 400,
					'fouten' => $fouten,
				)
			);
		}

		$slug      = isset( $body['slug'] ) && '' !== $body['slug'] ? sanitize_title( $body['slug'] ) : sanitize_title( $naam );
		$bijwerken = ! empty( $body['bijwerken'] );
		$bestaand  = get_page_by_path( $slug, OBJECT, self::POST_TYPE );

		if ( $bestaand && ! $bijwerken ) {
			return new WP_Error(
				'snackspert_bestaat_al',
				sprintf( 'Er bestaat al een restaurant met slug "%s". Stuur bijwerken=true om die te overschrijven.', $slug ),
				array(
					'status' => 409,
					'id'     => $bestaand->ID,
					'link'   => get_permalink( $bestaand ),
				)
			);
		}

		if ( ! empty( $body['dry_run'] ) ) {
			return rest_ensure_response(
				array(
					'dry_run'        => true,
					'zou_doen'       => $bestaand ? 'bijwerken' : 'aanmaken',
					'slug'           => $slug,
					'naam'           => $naam,
					'category'       => $categorie,
					'main_category'  => $hoofdcategorie ? $hoofdcategorie[0] : '',
					'diet'           => $dieet,
					'waarschuwingen' => $waarschuwingen,
				)
			);
		}

		/* --- post aanmaken of bijwerken --- */
		$postdata = array(
			'post_type'   => self::POST_TYPE,
			'post_title'  => $naam,
			'post_name'   => $slug,
			'post_status' => 'publish', // Direct live, geen conceptstap.
		);
		if ( ! empty( $body['ook_post_content'] ) ) {
			$postdata['post_content'] = $tekst;
		}
		if ( $bestaand ) {
			$postdata['ID'] = $bestaand->ID;
			$post_id        = wp_update_post( $postdata, true );
		} else {
			$post_id = wp_insert_post( $postdata, true );
		}
		if ( is_wp_error( $post_id ) ) {
			return $post_id;
		}

		/* --- hoofdfoto --- */
		$image = $this->resolve_image( $body, $post_id, $waarschuwingen );
		if ( is_wp_error( $image ) ) {
			// De post staat er al; melden wat er misging in plaats van stilletjes doorgaan.
			$waarschuwingen[] = 'Foto niet gekoppeld: ' . $image->get_error_message();
			$image            = null;
		}

		/* --- locatie --- */
		$locatie = $this->resolve_locatie( $body, $waarschuwingen );

		/* --- ACF-velden wegschrijven --- */
		$this->set_field( 'text', $tekst, $post_id );
		$this->set_field( 'category', $categorie, $post_id );
		$this->set_field( 'main_category', $hoofdcategorie ? $hoofdcategorie[0] : '', $post_id );
		if ( $dieet || null !== $this->field( 'diet' ) ) {
			$this->set_field( 'diet', $dieet, $post_id );
		}
		if ( isset( $body['adres'] ) ) {
			$this->set_field( 'address', sanitize_textarea_field( wp_unslash( $body['adres'] ) ), $post_id );
		}
		if ( $image ) {
			$this->set_field( 'image', (int) $image['id'], $post_id );
			set_post_thumbnail( $post_id, (int) $image['id'] ); // De app leest wp:featuredmedia.
		}
		if ( $locatie && ! empty( $locatie['id'] ) ) {
			$this->set_field( 'location', (int) $locatie['id'], $post_id );
		}
		$map = $this->build_map( $body );
		if ( $map ) {
			$this->set_field( 'map', $map, $post_id );
		} else {
			$waarschuwingen[] = 'Geen lat/lng meegegeven: deze zaak verschijnt niet op de kaart.';
		}

		clean_post_cache( $post_id );

		return rest_ensure_response(
			array(
				'id'             => $post_id,
				'slug'           => get_post_field( 'post_name', $post_id ),
				'link'           => get_permalink( $post_id ),
				'status'         => get_post_status( $post_id ),
				'bijgewerkt'     => (bool) $bestaand,
				'image'          => $image,
				'locatie'        => $locatie,
				'map'            => $map,
				'waarschuwingen' => $waarschuwingen,
			)
		);
	}

	/** Schrijft altijd op field key, zodat ACF de _veldnaam referentie meeneemt. */
	private function set_field( $naam, $waarde, $post_id ) {
		$field = $this->field( $naam );
		if ( ! $field ) {
			return false;
		}
		return update_field( $field['key'], $waarde, $post_id );
	}

	/* -------------------------------------------------------------- foto */

	/**
	 * Levert array{id:int,url:string} op. Drie manieren, in volgorde van
	 * voorkeur: een attachment-ID dat je al hebt, een bestand dat je base64
	 * meestuurt, of een URL die de server zelf binnenhaalt.
	 */
	private function resolve_image( $body, $post_id, &$waarschuwingen ) {
		if ( ! empty( $body['image_id'] ) ) {
			$id = (int) $body['image_id'];
			if ( 'attachment' !== get_post_type( $id ) ) {
				return new WP_Error( 'snackspert_geen_attachment', sprintf( 'ID %d is geen mediabestand.', $id ) );
			}
			return array(
				'id'  => $id,
				'url' => wp_get_attachment_url( $id ),
			);
		}

		require_once ABSPATH . 'wp-admin/includes/file.php';
		require_once ABSPATH . 'wp-admin/includes/media.php';
		require_once ABSPATH . 'wp-admin/includes/image.php';

		if ( ! empty( $body['image_base64'] ) ) {
			$bestandsnaam = ! empty( $body['image_filename'] )
				? sanitize_file_name( $body['image_filename'] )
				: sanitize_file_name( get_post_field( 'post_name', $post_id ) . '.jpg' );

			$binair = base64_decode( preg_replace( '#^data:[^;]+;base64,#', '', $body['image_base64'] ), true );
			if ( false === $binair || '' === $binair ) {
				return new WP_Error( 'snackspert_foto_ongeldig', 'image_base64 kon niet gedecodeerd worden.' );
			}
			if ( strlen( $binair ) > self::MAX_IMAGE ) {
				return new WP_Error( 'snackspert_foto_te_groot', sprintf( 'Foto is groter dan %d MB.', self::MAX_IMAGE / 1048576 ) );
			}

			$upload = wp_upload_bits( $bestandsnaam, null, $binair );
			if ( ! empty( $upload['error'] ) ) {
				return new WP_Error( 'snackspert_upload_mislukt', $upload['error'] );
			}
			return $this->attach( $upload['file'], $upload['url'], $post_id, $body );
		}

		if ( ! empty( $body['image_url'] ) ) {
			$tmp = download_url( esc_url_raw( $body['image_url'] ) );
			if ( is_wp_error( $tmp ) ) {
				return $tmp;
			}
			$bestand = array(
				'name'     => basename( parse_url( $body['image_url'], PHP_URL_PATH ) ),
				'tmp_name' => $tmp,
			);
			$id      = media_handle_sideload( $bestand, $post_id );
			if ( is_wp_error( $id ) ) {
				@unlink( $tmp );
				return $id;
			}
			if ( ! empty( $body['image_alt'] ) ) {
				update_post_meta( $id, '_wp_attachment_image_alt', sanitize_text_field( $body['image_alt'] ) );
			}
			return array(
				'id'  => (int) $id,
				'url' => wp_get_attachment_url( $id ),
			);
		}

		$waarschuwingen[] = 'Geen foto meegegeven; het item verschijnt zonder hoofdfoto.';
		return null;
	}

	private function attach( $pad, $url, $post_id, $body ) {
		$type = wp_check_filetype( $pad );
		if ( empty( $type['type'] ) || 0 !== strpos( $type['type'], 'image/' ) ) {
			@unlink( $pad );
			return new WP_Error( 'snackspert_geen_afbeelding', 'Het aangeleverde bestand is geen afbeelding.' );
		}

		$attachment_id = wp_insert_attachment(
			array(
				'post_mime_type' => $type['type'],
				'post_title'     => ! empty( $body['image_alt'] ) ? sanitize_text_field( $body['image_alt'] ) : get_the_title( $post_id ),
				'post_status'    => 'inherit',
			),
			$pad,
			$post_id
		);
		if ( is_wp_error( $attachment_id ) ) {
			return $attachment_id;
		}
		wp_update_attachment_metadata( $attachment_id, wp_generate_attachment_metadata( $attachment_id, $pad ) );
		if ( ! empty( $body['image_alt'] ) ) {
			update_post_meta( $attachment_id, '_wp_attachment_image_alt', sanitize_text_field( $body['image_alt'] ) );
		}

		return array(
			'id'  => (int) $attachment_id,
			'url' => $url,
		);
	}

	/* ------------------------------------------------------------ locatie */

	/**
	 * Zoekt de bestaande "locatie"-pagina bij een plaatsnaam. Wordt er geen
	 * gevonden, dan maken we er alleen een aan als daar expliciet om gevraagd is
	 * (maak_locatie_aan), want een half gevulde plaatspagina is erger dan geen.
	 */
	private function resolve_locatie( $body, &$waarschuwingen ) {
		if ( ! empty( $body['location_id'] ) ) {
			$id = (int) $body['location_id'];
			if ( self::LOC_TYPE !== get_post_type( $id ) ) {
				$waarschuwingen[] = sprintf( 'location_id %d is geen "%s"-pagina; koppeling overgeslagen.', $id, self::LOC_TYPE );
				return null;
			}
			return array(
				'id'         => $id,
				'naam'       => get_the_title( $id ),
				'aangemaakt' => false,
			);
		}

		$plaats = isset( $body['plaats'] ) ? sanitize_text_field( wp_unslash( $body['plaats'] ) ) : '';
		if ( '' === $plaats ) {
			$waarschuwingen[] = 'Geen plaats meegegeven; het item is niet aan een plaatspagina gekoppeld.';
			return null;
		}

		$gevonden = $this->find_locatie( $plaats );
		if ( $gevonden ) {
			return array(
				'id'         => $gevonden->ID,
				'naam'       => $gevonden->post_title,
				'aangemaakt' => false,
			);
		}

		if ( empty( $body['maak_locatie_aan'] ) ) {
			$waarschuwingen[] = sprintf(
				'Plaatspagina "%s" bestaat nog niet. Maak hem aan in wp-admin, of stuur maak_locatie_aan=true.',
				$plaats
			);
			return null;
		}

		$id = wp_insert_post(
			array(
				'post_type'   => self::LOC_TYPE,
				'post_title'  => $plaats,
				'post_name'   => sanitize_title( $plaats ),
				'post_status' => 'publish',
			),
			true
		);
		if ( is_wp_error( $id ) ) {
			$waarschuwingen[] = 'Plaatspagina aanmaken mislukt: ' . $id->get_error_message();
			return null;
		}

		$waarschuwingen[] = sprintf( 'Nieuwe plaatspagina "%s" aangemaakt (ID %d); controleer of die inhoudelijk klopt.', $plaats, $id );
		return array(
			'id'         => (int) $id,
			'naam'       => $plaats,
			'aangemaakt' => true,
		);
	}

	/** Exacte titelmatch eerst, dan slug. Bewust geen fuzzy match: fout gekoppeld is erger dan niet gekoppeld. */
	private function find_locatie( $plaats ) {
		$op_slug = get_page_by_path( sanitize_title( $plaats ), OBJECT, self::LOC_TYPE );
		if ( $op_slug ) {
			return $op_slug;
		}
		$posts = get_posts(
			array(
				'post_type'        => self::LOC_TYPE,
				'post_status'      => 'publish',
				'posts_per_page'   => 50,
				'title'            => $plaats,
				'suppress_filters' => false,
			)
		);
		if ( $posts ) {
			return $posts[0];
		}
		// Titel-match zonder hoofdlettergevoeligheid, voor "den haag" vs "Den Haag".
		$alle = get_posts(
			array(
				'post_type'      => self::LOC_TYPE,
				'post_status'    => 'publish',
				'posts_per_page' => -1,
			)
		);
		foreach ( $alle as $kandidaat ) {
			if ( 0 === strcasecmp( $kandidaat->post_title, $plaats ) ) {
				return $kandidaat;
			}
		}
		return null;
	}

	/* ---------------------------------------------------------------- map */

	/**
	 * Het google_map-veldtype van ACF bewaart een array. lat/lng/address zijn de
	 * enige sleutels die de front-end echt nodig heeft; de rest vult Google's
	 * autocomplete normaal aan en mag ontbreken.
	 */
	private function build_map( $body ) {
		if ( ! isset( $body['lat'], $body['lng'] ) || '' === $body['lat'] || '' === $body['lng'] ) {
			return null;
		}
		$lat = (float) $body['lat'];
		$lng = (float) $body['lng'];
		if ( $lat < -90 || $lat > 90 || $lng < -180 || $lng > 180 ) {
			return null;
		}

		$adres = isset( $body['adres'] ) ? trim( preg_replace( '/\s+/', ' ', wp_strip_all_tags( $body['adres'] ) ) ) : '';

		$map = array(
			'address' => $adres,
			'lat'     => $lat,
			'lng'     => $lng,
			'zoom'    => isset( $body['zoom'] ) ? (int) $body['zoom'] : 15,
		);
		foreach ( array( 'place_id', 'street_number', 'street_name', 'city', 'state', 'post_code', 'country' ) as $extra ) {
			if ( ! empty( $body[ $extra ] ) ) {
				$map[ $extra ] = sanitize_text_field( $body[ $extra ] );
			}
		}
		return $map;
	}

	/* ------------------------------------------------------------- schema */

	/**
	 * Leest de werkelijke situatie op de site uit: welke velden bestaan, welke
	 * keuzes ze hebben, en hoe de laatst gepubliceerde review ze daadwerkelijk in
	 * de database heeft staan. Daarmee zijn image/location/map te controleren
	 * zonder te hoeven gokken.
	 */
	public function get_schema( WP_REST_Request $request ) {
		$out = array(
			'acf_actief'   => $this->acf_ready(),
			'acf_versie'   => defined( 'ACF_VERSION' ) ? ACF_VERSION : null,
			'groep_key'    => self::GROUP_KEY,
			'post_types'   => array(),
			'velden'       => array(),
			'aantal_locaties' => 0,
		);

		foreach ( array( self::POST_TYPE, self::LOC_TYPE ) as $type ) {
			$object = get_post_type_object( $type );
			$out['post_types'][ $type ] = $object
				? array(
					'bestaat'      => true,
					'rest_base'    => $object->rest_base ? $object->rest_base : $type,
					'show_in_rest' => (bool) $object->show_in_rest,
					'aantal'       => (int) wp_count_posts( $type )->publish,
				)
				: array( 'bestaat' => false );
		}
		$out['aantal_locaties'] = isset( $out['post_types'][ self::LOC_TYPE ]['aantal'] )
			? $out['post_types'][ self::LOC_TYPE ]['aantal']
			: 0;

		if ( $this->acf_ready() ) {
			$groep = acf_get_field_group( self::GROUP_KEY );
			$out['groep'] = $groep
				? array(
					'titel'        => $groep['title'],
					'actief'       => ! empty( $groep['active'] ),
					'show_in_rest' => ! empty( $groep['show_in_rest'] ),
				)
				: null;

			foreach ( $this->fields() as $naam => $field ) {
				$out['velden'][ $naam ] = array(
					'key'           => $field['key'],
					'type'          => $field['type'],
					'multiple'      => ! empty( $field['multiple'] ),
					'return_format' => isset( $field['return_format'] ) ? $field['return_format'] : null,
					'choices'       => isset( $field['choices'] ) ? array_keys( (array) $field['choices'] ) : null,
				);
			}
		}

		// Ruwe meta van de nieuwste gepubliceerde review: de feitelijke opslagvorm.
		$laatste = get_posts(
			array(
				'post_type'      => self::POST_TYPE,
				'post_status'    => 'publish',
				'posts_per_page' => 1,
				'orderby'        => 'date',
				'order'          => 'DESC',
			)
		);
		if ( $laatste ) {
			$post   = $laatste[0];
			$sample = array(
				'id'    => $post->ID,
				'titel' => $post->post_title,
				'link'  => get_permalink( $post ),
				'ruwe_meta' => array(),
			);
			foreach ( array_keys( $this->fields() ) as $naam ) {
				$sample['ruwe_meta'][ $naam ] = get_post_meta( $post->ID, $naam, true );
			}
			$out['voorbeeld'] = $sample;
		}

		return rest_ensure_response( $out );
	}

	/** Plaatspagina's opzoeken, zodat de client vooraf kan controleren of een plaats bestaat. */
	public function get_locaties( WP_REST_Request $request ) {
		$zoek  = $request->get_param( 'zoek' );
		$posts = get_posts(
			array(
				'post_type'      => self::LOC_TYPE,
				'post_status'    => 'publish',
				'posts_per_page' => $zoek ? 50 : -1,
				's'              => $zoek ? sanitize_text_field( $zoek ) : '',
				'orderby'        => 'title',
				'order'          => 'ASC',
			)
		);

		$uit = array();
		foreach ( $posts as $post ) {
			$uit[] = array(
				'id'   => $post->ID,
				'naam' => $post->post_title,
				'slug' => $post->post_name,
			);
		}
		return rest_ensure_response( $uit );
	}
}

Snackspert_Review_API::boot();

endif;
