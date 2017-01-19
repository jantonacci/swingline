Lumbergh - Framework for Python log review and filtering

Greetings people,

Jason here. I like BASH and Python and meat (that's what I'm made of!). 
I have had breakfast burritos for lunch and find them superior to lunch 
burritos.

Are you using the new TPS Report cover sheets?  The old TPS reports used custom
code to identify, and search files.  Lumbergh is here to remind you not to do 
them.  MMmmmm-kay?  Pass Lumbergh a list of file paths and he can search them 
all and return a dictionary: file paths as keys and content lists as values.

Creating working code faster. Spend less time on code not directly related to 
the objective!  Who wants to work week-ends?

Most Base class methods take the same three kwargs: string (list), regex (list) and file (list).

Other classes Logger and Opener support Base, but can be used on their own.

Ciao,
Jason Antonacci
https://about.me/jason.antonacci

Example: 

    import lib.lumbergh, re

    base=lib.lumbergh.Base()

    base.f_search(string=['Generated'],
                  file=['test_files/lipsum.txt', 'test_files/lipsum.txt.gz', 'test_files/lipsum.txt.bz2'])

    base.c_search(regex=[re.compile(r'paragraph', re.IGNORECASE)], file=['test_files/lipsum.txt'])
