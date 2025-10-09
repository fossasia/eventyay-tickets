// TODO
// - connection to a session -> room
// - chat room
// random examples from https://ur.umbc.edu/poster-presentation-examples/
// QUESTIONS
// - does the detail page need a longer body text, or is `abstract` the same for list and details?
export default [{
	id: '1',
	title: 'Comparing Emotional Regulation Strategies to Predict Satisfaction with Life and Perceived Stress',
	authors: ['Mobolanle Adebesin', 'Meagan M. Graydon, M.A.', 'Daniel J. Knoblach, M.A.', 'Taylor B. Crouch, M.A.', 'Carlo C. DiClemente, Ph.D.'],
	presenters: [{
		id: 'eeb3dc26-8fe7-4564-96f9-36fa30ec6150',
		profile: {
			avatar: {identicon: '17743ee3-6659-4757-824e-9982a1457814'},
			display_name: 'Presenter McPresentface'
		}
	}],
	abstract: 'Individuals use emotional regulation (ER) strategies when dealing with various life circumstances. However, the methods individuals use to regulate emotions can impact life satisfaction and stress levels.1 Two common ER strategies include cognitive reappraisal (changing how one thinks about an event) and expression suppression (concealing one’s reaction). Past studies have shown cognitive reappraisal predicts higher life satisfaction and lower stress as compared to expression suppression. The current study investigated these relationships using data obtained from a doctoral dissertation study involving a national convenience sample of young adults completing the survey on the internet (N = 561). We hypothesized that emotion regulation strategies used would predict reported life satisfaction and perceived stress. Results of multiple regression analyses revealed that cognitive reappraisal positively predicted life satisfaction (β = .33, p<.001) and negatively predicted perceived stress (β = -.22, p<.001). Expression suppression had an inverse relation with both outcomes [life satisfaction (β = -.18, p<.001), perceived stress (β = .18, p<.001)]. These results support the importance of understanding young adults’ emotion regulation strategies in order to assist them to manage stress and build lives that have higher levels of emotional well-being.',
	category: 'Psychology',
	tags: ['tag 1', 'tag 3'], // probably normalize and multi-lang this?
	likes: '42',
	poster_preview: 'http://localhost:8375/media/pub/sample/f4c96ec8-4378-440b-8af9-a903353f1bc9.u9ktSuDTNIae.png',
	poster_url: 'http://localhost:8375/media/pub/sample/10ec2ab1-8aec-4f52-a8d9-77680038cff2.tnTDYe1bitJ4.pdf',
	files: [{
		display_text: 'Full Paper',
		url: 'somepaper.pdf'
	}],
	channel: 'f28e2c91-f860-48a7-917b-7a665cfeb590'
}, {
	id: '2',
	title: 'Experimental and Computational Analysis of Lift Generation by Wing Morphing Bird',
	authors: ['Theophilus Aluko', 'Dr. Meilin Yu, Assistant Professor, Mechanical Engineering', 'Jamie Gurganus, Instructor, Mechanical Engineering'],
	presenters: [{
		id: 'eeb3dc26-8fe7-4564-96f9-36fa30ec6150',
		profile: {
			avatar: {identicon: '17743ee3-6659-4757-824e-9982a1457814'},
			display_name: 'Presenter McPresentface'
		}
	}],
	abstract: 'This research aims to study and mimic the lift of a barn swallow via computational and experimental analysis, by meeting finite dynamic constraints such as flapping amplitudes and frequency. This bird was selected because of its maneuverability, efficiency and conical morphing wing-flapping motion. An animation of a simplified lifting process was obtained by creating a three-dimensional scan of a representative bird from the Smithsonian National Museum of Natural History. In addition to the animation, we constructed a physical aerial robot prototype that mimicked the take-off process of the bird in its natural environment. Using the physical model, the generated lift force caused by the morphing flapping structure was measured and then compared with the force derived by a conventional flapping structure. To compare the experiment with the computation, coefficient of lift was obtained for each method. Our analysis and measurements support the hypothesis that the lift generation is highly affected by a characterization of changes in the bird’s wing due to geometry. In particular we hypothesize that leading-edge vortices (LEVs) play an important role in lift generation and should be further parameterized for the making of safer, more efficient wing-morphing commercial aircraft.',
	category: 'Mechanical Engineering',
	tags: ['tag 2', 'tag 3'], // probably normalize and multi-lang this?
	likes: '123',
	poster_preview: '/poster-2.png',
	poster_url: 'https://ur.umbc.edu/files/2016/06/alukoTheophilusSm.pdf',
	files: [{
		display_text: 'Full Paper',
		url: 'somepaper.pdf'
	}]
}, {
	id: '3',
	title: 'Identification of Molecular Properties to Cluster Genetic Markers of Cardiovascular Disease',
	authors: ['Ann G Cirincione', 'Kaylyn L. Clark', 'Maricel G. Kann'],
	presenters: [{
		id: 'eeb3dc26-8fe7-4564-96f9-36fa30ec6150',
		profile: {
			avatar: {identicon: '17743ee3-6659-4757-824e-9982a1457814'},
			display_name: 'Presenter McPresentface'
		}
	}],
	abstract: 'Cardiovascular disease (CVD) is the leading cause of death worldwide in both men and women. It is especially prevalent in the United States, where it is responsible for one out of every four deaths. Genetic markers linked to susceptibility to CVD have been identified, however a large number are still unknown. We have mapped 15% of disease variants from the Human Gene Mutation Database (HGMD), 62% from the Clinical Variance database (ClinVar), and 28% from the Universal Protein Resource (UniProt) to the Online Mendelian Inheritance in Man (OMIM), which has direct links to the Human Phenotype Ontology (HPO). From these variants, we will extract the subset linked to CVD, as well as increase coverage of variants mapped to OMIM. We aim to use machine learning techniques and algorithms to cluster new genetic variants to molecular properties of known CVD markers in order to better diagnose and treat individual patients. For this purpose we have compiled a list of molecular properties including protein domain interactions, common gene ontologies, and metabolic pathways. In the future, these methods will be used to match individual genome data to corresponding CVD clusters, developing new diagnostic tools to personalize and optimize diagnosis of CVD.',
	category: 'Biological Sciences',
	tags: ['tag 4'], // probably normalize and multi-lang this?
	likes: '13',
	poster_preview: '/poster-3.png',
	poster_url: 'https://ur.umbc.edu/files/2016/06/cirincioneAnnSm.pdf',
	files: [{
		display_text: 'Full Paper',
		url: 'somepaper.pdf'
	}]
}]
