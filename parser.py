from lexer import *
from expression_handler.calculator import Calculator

_ANNOUNCEMENT = 'announcement'
_INITIALIZE = 'initialize'

_GETITEM = 'getitem'
_SETITEM = 'setitem'
_REFERENCE = 'reference'


class Parser:

    def __init__(self, lexer):
        self.lexer = lexer
        self.memory = types_.Memory()

        self.token = None
        self.index = None

    def _step(self):
        self.lexer.next_token()
        self.ch = self.lexer.ch
        self.name = self.lexer.name
        self.value = self.lexer.value
        self.token = self.lexer.token

    def is_WS_before(self, token, /):
        #ch = self.ch # не будет работать
        if self.token is token:
            if self.ch == ' ':
                raise SyntaxError(f'WS before {token}')
            return False
        else:
            raise SyntaxError(f'Ожидается другой токен {token} получен {self.token}')

    # arr[<expression>] = {<expression>, <expression>, ..., <expression>}
    def parse_array(self, name, pointer=False, *, mode):

        def define_action(dimension):
            if isinstance(dimension, int):
                if mode == _ANNOUNCEMENT:
                    self._step()
                    return types_.ARRAY(length=value)

                elif mode == _GETITEM:
                    variable = self.memory.get_by_name(name, throw=True)
                    return variable.value[dimension]

                elif mode == _SETITEM:
                    self._step()
                    self.memory.get_by_name(name, throw=True)
                    return dimension

                elif mode == _REFERENCE:
                    start = self.memory.get_by_name(name, throw=True)
                    return start.id + dimension
            else:
                raise SyntaxError('Define_action type must be <INTEGER> and not <FRACTIONAL>')

        if pointer:
            raise SyntaxError('Not implemented feature')

        self._step()
        value = self.calculate_expression(stop_tokens=(RSBR,))  # in [...]
        return define_action(value)


    def array_init(self, controller: types_.Controller):
        temp_array = []
        if self.token is LBRC:
            self._step()
            while True:
                temp_array.append(self.calculate_expression(stop_tokens=(COMMA, RBRC)))
                if self.token is RBRC:
                    break
                self._step()

            if controller.length == 0:
                array = types_.ARRAY(length=len(temp_array))
                variable = controller.variable

                variable.value = array
                controller = types_.Controller(variable)

            elif controller.length >= len(temp_array):
                zeros = [0 for _ in range(controller.length - len(temp_array))]
                temp_array.extend(zeros)
            else:
                raise SyntaxError('controller.length < len(temp_array)')

            list(map(lambda element: controller.append(element), temp_array))
            self._step()
        else:
            raise SyntaxError(f'expected token <{{> received {self.token}')

    def set_array_elem(self, controller: types_.Controller):
        controller.setitem(self.calculate_expression(), self.index)

    # нужно передавать как у
    def pointer_init(self):
        # token = self.lexer.token
        if self.token is REFERENCE:
            self._step()
            if self.token is VARIABLE:
                variable = self.memory.get_by_name(self.name, throw=True)
                self._step()
                if self.token is SEMICOLON:
                    return variable.__class__, variable.id

                elif not self.is_WS_before(LSBR):
                    self._step()
                    id = self.parse_array(variable.name, variable.pointer, mode=_REFERENCE)
                    return variable.__class__, id

        elif self.token is VARIABLE:
            variable = self.memory.get_by_name(self.name)
            if variable.pointer:
                self._step()
                return variable.__class__, variable.reference
            else:
                raise SyntaxError(f'<{variable.name}> not a pointer variable')
        else:
            raise SyntaxError(f'Unexpected token {self.token} expected <REFERENCE> or <VARIABLE>')

    def _scroller(self, token):
        while self.token != token:
            self._step()
            if self.token is EOF:
                raise SyntaxError(f'Token not found <{token}>')

    def _expression_parser(self, stop_tokens: tuple):
        expression = Calculator()
        ch = None
        star_flag = None

        while True:
            if self.token is VARIABLE:
                name = self.name

                if (variable := self.memory.get_by_name(name, throw=True)):
                    # when parse element is array element
                    if isinstance(variable.value, types_.ARRAY):
                        self._step()
                        if not self.is_WS_before(LSBR):
                            expression.token_storage.append(str(self.parse_array(name, mode=_GETITEM)))
                    # when parse element is variable
                    else:
                        variable = self.memory.get_by_name(name)

                        if variable.pointer:
                            if star_flag and ch != ' ':
                                expression.token_storage.pop()
                                id = int(variable.reference)
                                value = str(self.memory.get_by_id(id).value[id])
                                expression.token_storage.append(value)
                            else:
                                raise SyntaxError('Error in pointer construction')
                        else:
                            if variable.value is not None:
                                expression.token_storage.append(str(variable.value))
                            else:
                                raise SyntaxError(f'Variable - <{name}> not defined')

            elif self.token is CONSTANT:
                expression.token_storage.append(str(self.value))

            elif self.token is LBR:
                expression.token_storage.append('(')

            elif self.token is RBR:
                expression.token_storage.append(')')

            elif self.token.__base__ is OPERATOR:
                expression.token_storage.append(self.token.operator)
                if self.token is MUL:
                    star_flag = True
                    ch = self.ch

            elif self.token is QUESTION_MARK:
                stop_tokens = (QUESTION_MARK,)

            elif self.token.__base__ is LOGIC:
                expression.token_storage.append(self.token.operator)

            elif self.token in stop_tokens:
                break

            else:
                raise SyntaxError(
                    f'unacceptable token - <{self.token}> in expression expected token {stop_tokens}')

            self._step()

        return expression, stop_tokens

    def calculate_expression(self, stop_tokens=(SEMICOLON,)):
        expression, stop_tokens = self._expression_parser(stop_tokens)

        if QUESTION_MARK in stop_tokens:
            if expression.find_value():
                expression, *_ = self._expression_parser(stop_tokens=(COLON,))
                self._scroller(token=SEMICOLON)
            else:
                self._scroller(token=COLON)
                expression, *_ = self._expression_parser(stop_tokens=(SEMICOLON,))

        if RSBR in stop_tokens and not expression.token_storage:
            return 0 # to initialize an array of undeclared lengths

        return expression.find_value()

    def _initializer(self, variable):

        if isinstance(variable.value, types_.ARRAY):
            if self.index is not None:
                self.set_array_elem(types_.Controller(variable))
            else:
                self.array_init(types_.Controller(variable))

        elif variable.pointer:
            type, reference = self.pointer_init()
            if variable.__class__ is not type:
                raise SyntaxError(f'Different types : {variable.__class__} and {type}')
            variable.reference = reference

        else:
            variable.value = self.calculate_expression()

    def _constructor(self, name, pointer, mode):
        if self.memory.get_by_name(name) is None:
            if mode == _INITIALIZE:
                raise SyntaxError(f'The variable <{name}> has not been declared')

            self._step()
            self.variable = self.type_(name, pointer)

            if self.token in (COMMA, SEMICOLON, ASSIGNMENT):
                self.memory.append(self.variable)

            elif not self.is_WS_before(LSBR):
                array = self.parse_array(name, pointer, mode=mode)
                self.variable.value = array
                self.memory.append(self.variable)
        else:
            if mode == _ANNOUNCEMENT:
                raise SyntaxError(f'Redefinition of <{name}>')

            self.variable = self.memory.last_viewed
            self._step()

            if self.token is ASSIGNMENT:
                pass
            elif not self.is_WS_before(LSBR):
                self.index = self.parse_array(name, pointer, mode=_SETITEM)
            else:
                raise SyntaxError(f'unacceptable token - <{self.token}>')


    def _classifier(self, mode):
        if mode == _ANNOUNCEMENT:
            self._step()

        if self.token is MUL:
            self._step()
            if self.token is VARIABLE:
                self._constructor(name=self.name, pointer=True, mode=mode)

        elif self.token is VARIABLE:
            self._constructor(name=self.name, pointer=False, mode=mode)

    def _determinator(self, mode: str):
        """
        Determines the next step by set mode

        Modes: _ANNOUNCEMENT, _INITIALIZE

        In _ANNOUNCEMENT parses lines similar to:
        * type var1, *var2, var3[<expr>], ...;

        In _INITIALIZE parses lines similar to:
        * type var = ...;
        * type var[] = ...;
        After the assignment operator, control passes to the initializer,
        which parses the expression in accordance with the declaration
        """
        if mode == _ANNOUNCEMENT:
            self.type_ = self.token

        self._classifier(mode)
        if self.token is ASSIGNMENT:
            self._step()
            self._initializer(self.variable)
        else:
            if mode == _ANNOUNCEMENT:
                while self.token is not SEMICOLON:
                    if self.token is COMMA:
                        self._step()
                    self._classifier(mode)
            else:
                raise SyntaxError('You cannot initialize more than one variable in a declaration line')

    def parse(self):
        self._step()
        while self.token != EOF:
            if self.token in Lexer.TYPES.values():
                self._determinator(mode=_ANNOUNCEMENT)
            else:
                self._determinator(mode=_INITIALIZE)

            self._step()

if __name__ == '__main__':
    l = Lexer('int a[] = {77 -(91*2)/3, 5}; int *q = &a; a[0] = *q + 2;')
    # l = Lexer('int a[] = {77 -(91*2)/3}; int c = 33;')
    # l = Lexer('int a[4] = {7 - 99*2- (88/3),3, 566.2, 4554-888};')
    p = Parser(l)
    p.parse()
    print(p.memory)
    # print(p.calculate_expression())
