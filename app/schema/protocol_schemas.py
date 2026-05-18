OUTLINE_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "protocolVersion",
        "language",
        "presentationTitle",
        "targetSlideCount",
        "sections",
    ],
    "properties": {
        "protocolVersion": {"type": "string", "const": "ppt-narrative-outline.v1"},
        "language": {"type": "string", "minLength": 2, "maxLength": 20},
        "presentationTitle": {"type": "string", "minLength": 4, "maxLength": 120},
        "targetSlideCount": {"type": "integer", "minimum": 3, "maximum": 50},
        "sections": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["sectionId", "sectionTitle", "sectionObjective", "slideRange", "slides"],
                "properties": {
                    "sectionId": {"type": "string", "pattern": "^sec-[0-9]{2}$"},
                    "sectionTitle": {"type": "string", "minLength": 2, "maxLength": 80},
                    "sectionObjective": {"type": "string", "minLength": 8, "maxLength": 200},
                    "slideRange": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["start", "end"],
                        "properties": {
                            "start": {"type": "integer", "minimum": 1, "maximum": 50},
                            "end": {"type": "integer", "minimum": 1, "maximum": 50},
                        },
                    },
                    "slides": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["slideId", "slideNumber", "slideRole", "slideTitle", "keyPoints"],
                            "properties": {
                                "slideId": {"type": "string", "pattern": "^slide-[0-9]{3}$"},
                                "slideNumber": {"type": "integer", "minimum": 1, "maximum": 50},
                                "slideRole": {
                                    "type": "string",
                                    "enum": ["cover", "toc", "transition", "content", "case-study", "summary", "qa", "appendix"],
                                },
                                "slideTitle": {"type": "string", "minLength": 2, "maxLength": 80},
                                "keyPoints": {
                                    "type": "array",
                                    "minItems": 2,
                                    "maxItems": 5,
                                    "items": {"type": "string", "minLength": 2, "maxLength": 140},
                                },
                                "notes": {"type": "string", "maxLength": 300},
                            },
                        },
                    },
                },
            },
        },
    },
}


PAGE_CONTENT_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["protocolVersion", "language", "presentationTitle", "researchPolicy", "slides"],
    "properties": {
        "protocolVersion": {"type": "string", "const": "ppt-page-content.v1"},
        "language": {"type": "string", "minLength": 2, "maxLength": 20},
        "presentationTitle": {"type": "string", "minLength": 4, "maxLength": 120},
        "researchPolicy": {
            "type": "object",
            "additionalProperties": False,
            "required": ["triggerReason", "depthLevel", "sourcePriority"],
            "properties": {
                "triggerReason": {"type": "string", "enum": ["user_requested", "insufficient_input", "fact_verification"]},
                "depthLevel": {"type": "string", "enum": ["light", "standard", "deep"]},
                "sourcePriority": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "items": {
                        "type": "string",
                        "enum": ["official_sites", "government_reports", "academic_sources", "authoritative_media", "industry_reports"],
                    },
                },
                "maxSourcesPerSlide": {"type": "integer", "minimum": 1, "maximum": 8},
            },
        },
        "slides": {
            "type": "array",
            "minItems": 1,
            "maxItems": 50,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "slideId",
                    "slideNumber",
                    "slideRole",
                    "pageGoal",
                    "slideTitle",
                    "coreMessage",
                    "displayBullets",
                    "keyData",
                    "evidencePack",
                    "actionableTakeaway",
                    "speakerNotes",
                ],
                "properties": {
                    "slideId": {"type": "string", "pattern": "^slide-[0-9]{3}$"},
                    "slideNumber": {"type": "integer", "minimum": 1, "maximum": 50},
                    "slideRole": {
                        "type": "string",
                        "enum": ["cover", "toc", "transition", "content", "case-study", "summary", "qa", "appendix"],
                    },
                    "pageGoal": {"type": "string", "minLength": 8, "maxLength": 120},
                    "slideTitle": {"type": "string", "minLength": 2, "maxLength": 80},
                    "coreMessage": {"type": "string", "minLength": 12, "maxLength": 140},
                    "displayBullets": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 5,
                        "items": {"type": "string", "minLength": 2, "maxLength": 120},
                    },
                    "keyData": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["label", "value", "unit", "year", "sourceRefId"],
                            "properties": {
                                "label": {"type": "string", "minLength": 2, "maxLength": 60},
                                "value": {"type": "number"},
                                "unit": {"type": "string", "minLength": 1, "maxLength": 20},
                                "year": {"type": "integer", "minimum": 1990, "maximum": 2100},
                                "sourceRefId": {"type": "string", "pattern": "^src-[0-9]{3}$"},
                            },
                        },
                    },
                    "evidencePack": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "sourceRefId",
                                "claim",
                                "sourceTitle",
                                "sourceType",
                                "url",
                                "publishDate",
                                "credibility",
                                "quote",
                            ],
                            "properties": {
                                "sourceRefId": {"type": "string", "pattern": "^src-[0-9]{3}$"},
                                "claim": {"type": "string", "minLength": 2, "maxLength": 180},
                                "sourceTitle": {"type": "string", "minLength": 2, "maxLength": 120},
                                "sourceType": {
                                    "type": "string",
                                    "enum": ["official_sites", "government_reports", "academic_sources", "authoritative_media", "industry_reports"],
                                },
                                "url": {"type": "string", "maxLength": 300},
                                "publishDate": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                                "credibility": {"type": "string", "enum": ["high", "medium"]},
                                "quote": {"type": "string", "maxLength": 220},
                            },
                        },
                    },
                    "actionableTakeaway": {"type": "string", "maxLength": 120},
                    "speakerNotes": {"type": "string", "minLength": 10, "maxLength": 300},
                },
            },
        },
    },
}
