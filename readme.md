## Format Code for Sublime Text

Format or prettify code and text in selections or files - very configurable.

### Features

- you can use any formatter you like if they provide a command line tool :)
- format on save (can be toggled)
- format selections by creating a temporal file (on the same folder as the file being formatted)
- format unsaved files by creating a temporal file (on your os temp folder)
- guess file type by syntax in case the extension isn't obvious (ex .prettierrc == json)
- does not modify code if changed since the time we started formatting (no race condition)
- does not modify code if the result is the same (no undo trashing)
- keeps yours selections (when not applied on save xD because well ST reasons)
- ignore files via binary_file_patterns (it does not check for pattern only for substring)

### Languages

Support for languages must be installed by the user because you can use any formatting tool you wish if they provide a command line tool. Some examples:

#### js, json, jsx, php, css

npm install -g prettier

#### html

npm install -g js-beautify

#### python

pip install black

#### Adding/modify Support For Languages

You install the command line tool you want to use and be sure is on path

Then you just, copy from

Preferences > Package Settings > Format > Settings - Default

and paste modified/added formatters in

Preferences > Package Settings > Format > Settings - User

The configuration is very straightforward, an example:

```
{
	"format": {
		"jsx": {
			// the file extension will use this formatter

			/* the command line tool to which we can append a file path to format it */
			"command": ["prettier", "--config", "--write"],

			/* optional: Sublime Text syntax name for when the file has no extension */
			"syntax contains": "javascript",

			/*	optional: Even if we know that a file is a json, like for example ".prettierrc"
				The command line tool may not know ".prettierrc" is a json
				and will not be able to format it throwing some error. Example

				> prettier --write -- ./.prettierrc

				By looking for the error they give in stderr we can "try again"
				on a temporal file to include the "obvious" extension
				for example changing it to: ".prettierrc.json" giving:

				> prettier --write -- ./.prettierrc.json

				putting the result back in ".prettierrc"
			*/
			"on unrecognised": "No parser could be inferred",

			/* optional: you can pretend to be other extension if that may helps you*/
			"pretend to be": "jsx"
		},
	}
}
```

#### Usage

CTRL+SHIFT+P, then type: Format Code

or

CTRL+S

#### Ignoring

To ignore a file add it to the binary_file_patterns of sublime settings