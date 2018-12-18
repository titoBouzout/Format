## Format Code for Sublime Text

Format or prettify code and text in selections or files(saved or not) with any command line tool you wish.

### Features

- format on save (can be toggled)
- file save without formatting
- format selections by creating a temporal file (on the same folder as the file being formatted so formatting options in config files are respected)
- format unsaved files by creating a temporal file (on your os temp folder)
- could guess the file type by syntax in case the extension isn't obvious (ex .prettierrc == json)
- it does not modify code if changed since the time we started formatting
- it does not modify code if the result is the same (no undo trashing)
- ignore files via binary_file_patterns (it does not check for pattern only for substring)
- experimental live formatting after some seconds passed

### Languages

Support for languages must be installed by the user because you can use any formatting tool you wish if they provide a command line tool. Some examples:

#### js, json, jsx, php, css

npm install -g prettier

#### html

npm install -g js-beautify

#### python

pip install black

#### xml

npm install -g pretty-xml

#### Adding/modify Support For Languages

You install the command line tool you want to use and be sure is on path

Then you just, copy from

Preferences > Package Settings > Format > Settings - Default

and paste modified/added formatters in

Preferences > Package Settings > Format > Settings - User

The configuration is very straightforward, Stdout option is about giving the formatter stdin and taking stdout.

#### Usage

CTRL+SHIFT+P, then type: Format Code

or

CTRL+S

#### Ignoring

To ignore a file add it to the binary_file_patterns of sublime settings