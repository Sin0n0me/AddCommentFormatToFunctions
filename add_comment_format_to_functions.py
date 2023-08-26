import re
import sys
import os
import glob
from enum import Enum, auto

ENCODING_TYPE = 'UTF-8-SIG'
TARGET_FILE_NAME_LIST = 'check_list.txt'
TARGET_FILE_EXTENDS = ['h', 'hpp']
# もっとあるけど使ってないので一旦以下以下リストのみ
MODIFIER = [
    'const',
    'constexpr',
    'consteval',
    'static',
    'virtual',
    'explicit',
    'volatile',
    'restrict',
    'typedef',
    'inline',
    '__inline',
    '__forceinline',
    '__align',
    'extern',
    '__cdecl',
    '__clrcall',
    '__stdcall',
    '__fastcall',
    '__thiscall',
    '__vectorcall',
]

TEST_PATTERN = [
    'void hoge(void);',
    'Hoge hoge(void);',
    '__thiscall virtual const Hoge* hogehoge( void) const override;',
    'explicit Hoge(void ) : fuga(hoge){',
    'Hoge(void) : fuga(hoge) {',
    'Hoge(void):fuga() {',
    'Hoge(void) :   Fuga::fuga() {',
    'void Hoge(const int i = []()->int{return 0;});',
    'class Hoge {',
    'struct Hoge {',
    'class Hoge : public Fuga {',
    'void Hoge<T> hoge();',
    'void Hoge<T, U> hoge(const U<S> fugafuga);',
    'const auto itr = Hoge::map.find(key);',
    'const decltype(hoge)::const_iterator itr = Hoge::map.find(key);',
    'const Hoge hoge = std::make_shared<T>();',
    'Hoge::Fuga operator[](const Hoge::Fuga& index) const noexcept;',
    'Hoge::Fuga operator[](const Hoge::Fuga& index) const noexcept(false);',
    'Hoge<T>::Fuga operator[](const Hoge::Fuga& index) const noexcept(false);',
    'virtual void hoge(const Hoge::Fuga<float, 4, void>* fuga, const int nya) const = 0;',
    'Hoge hoge(void) = delete;',
    'Hoge(void) = delete;',
    'const Hoge& operator=(const Hoge&) = delete;',
    'template <>',
    'template <class T>',
    'template <class T,class U>',
    'template <template <class> class T>',
    'template <template <class> class T, class U>',
    'template <template <class> class T, template <class, class> class U>',
]

'.*\s*=\s*(default|delete)\s*;'
# クラス
EXCLUDE_CLASS_PATTERN = re.compile(
    '\s*(class|struct)\s*([a-zA-Z0-9_]+).*{'
)
EXCLUDE_IGNORE_PATTERN = re.compile(
    '[\*\.\s\(\)_:<>a-zA-Z0-9]+[=][\*\.\s\(\)_:<>a-zA-Z0-9]+\(.*\).*(;|{)'
)
MINIMUM_PATTERN = re.compile(
    '.*\(.*\).*(;|{)'
)
# ()が含まれるか判定(その行が関数かどうかの判定)
# もう少しよい正規表現のやり方あると思う...
FUNCTION_PATTERN = re.compile(
    '\s*([a-zA-Z_:<>]+[a-zA-Z0-9]*[\s\*&]+)+.*\(.*\)[=0a-z\s]*[;{]'
)

CONSTRUCTOR_PATTERN = re.compile(
    '.*\((.*)\)\s*[:]\s*[_a-zA-Z0-9]+\(.*\)\s*[=0a-z\s]*{'
)

FUNCTION_RETURN_TYPE_PATTERN = re.compile(
    '\s*(([a-zA-Z_]+[a-zA-Z0-9]*[\s\*&]+)+)+.*\(.*\).*'
)

# return hoge::opetator++(); のような関数を弾く用
EXCLUDE_RETURN_PATTERN = re.compile(
    '\s*return\s*([_a-zA-Z]+[a-zA-Z0-9]*[\s\*&]+)*.*\(.*\)[=0a-z\s]*[;{]'
)

FUNCTION_PARAM_PATTERN = re.compile(
    '.*\((.*)\).*'
)

TEMPLAE_PATTERN = re.compile(
    '\s*template\s*<(.*)>\s*'
)

DEFAULT_ARGS_PATTERN = re.compile(
    '(.*)=.*'
)

VOID_PATTERN = re.compile(
    '\s*void\s*'
)

NOEXCEPT_PATTERN = re.compile(
    '.*\((.*)\)[a-z0-9\s]*noexcept\s*\(.*\)\s*[;{]'
)

DELETE_PATTERN = re.compile(
    '.*\(.*\).*\s*=\s*delete\s*;'
)


class FunctionReturnType(Enum):
    Type = auto()
    Void = auto()
    Constructor = auto()


def test():
    PATTERN = [
        EXCLUDE_CLASS_PATTERN,
        EXCLUDE_IGNORE_PATTERN,
        MINIMUM_PATTERN,
        FUNCTION_PATTERN,
        EXCLUDE_RETURN_PATTERN,
        FUNCTION_PARAM_PATTERN,
        TEMPLAE_PATTERN,
        DEFAULT_ARGS_PATTERN,
        VOID_PATTERN,
        NOEXCEPT_PATTERN,
        DELETE_PATTERN
    ]

    for test in TEST_PATTERN:
        print(f'----------------')
        print(f'test case:{test}')
        for pattern in PATTERN:
            match = pattern.match(test)
            print(f'pattern:{pattern}')
            if match:
                print(f'> match:{match.group(0)}')
                print(f'> groups:{match.groups()}')
            else:
                print(f'> not match')


def get_define_return_type(modifier_and_return_type: str, debug_mode=False) -> FunctionReturnType:
    # *があるか判定
    # *が存在する場合,返す型が存在するのでフラグを立てる(唯一返さない可能性のあるvoid型がvoid*になるので)
    if '*' in modifier_and_return_type:
        return FunctionReturnType.Type

    # 修飾子リストに一致するものを除去していき最終的に残った文字列で判定する
    split_lines = re.split(r'\s', modifier_and_return_type)

    # 空文字が含まれるので削除
    split_lines = list(filter(lambda val: val != '', split_lines))

    # 抽出した文字列と修飾子リストと共通する部分を抽出する
    common = set(MODIFIER) & set(split_lines)

    # 抽出した文字列と共通部分と差分をとることで型名が分かる
    diff = list(set(common) ^ set(split_lines))

    # 差分がない場合はコンストラクタの可能性が高いのでfalseを返す
    if diff == []:
        return FunctionReturnType.Constructor

    # voidは戻り値無しとしてfalseを返す
    if diff[0] == 'void':
        return FunctionReturnType.Void

    if debug_mode:
        print(f'modifier and return type:{split_lines}')
        print(f'hit keyword:{list(common)}')
        print(f'diff:{diff}')

    return FunctionReturnType.Type


def get_template_param_comment(template_arguments: list[str], indent, debug_mode=False) -> list[str]:
    if debug_mode:
        print(template_arguments)

    doxygen_comment = []
    for template_args in template_arguments:
        template_args = re.split(r'\s', template_args)[-1]
        doxygen_comment.append(f'{indent}* @tparam {template_args} ')

    return doxygen_comment


def get_func_param_comment(func_args: str, indent) -> list[str]:
    doxygen_comment = []

    # noexcept()~の場合noexceptの()を習得するので修正
    param = func_args
    match = NOEXCEPT_PATTERN.match(func_args)
    if match:
        param = match.group(1)

    # 継承元に引数を渡すヘッダに展開されたコンストラクタか判定
    # Hoge(hoge):Fuga(hoge)による二重にreturnを書いてしまうのとスーパークラスに渡す引数をparamに書いてしまうので
    super_class_args = CONSTRUCTOR_PATTERN.match(param)
    param = FUNCTION_PARAM_PATTERN.match(param)

    # 引数の判定
    param = super_class_args if super_class_args else param
    if not param:
        return doxygen_comment
    param = param.group(1)

    # voidでないかチェック
    if VOID_PATTERN.match(param):
        return doxygen_comment

    # templateによる,で後続の分割処理に引っかかるので事前に削除
    param = re.sub('<([a-zA-Z0-9:_\s]*[,]?)*>', '', param)

    param_lines = param.split(sep=',')
    for param_line in param_lines:

        # デフォルト引数が含まれるかチェック
        match = DEFAULT_ARGS_PATTERN.match(param_line)
        if match:
            # 空文字が含まれるので削除
            variable_name = list(filter(lambda val: val != '', re.split(r'\s', match.group(1))))[-1]
        else:
            variable_name = re.split(r'\s', param_line)[-1]

        doxygen_comment.append(
            f'{indent}* @param {variable_name} '
        )

    return doxygen_comment


# 修飾子 戻り値の型 関数名(修飾子 型 変数名) 修飾子 {}
def check_function_comment(file_path, debug_mode=False, nobackup_mode=False):
    if debug_mode:
        print('----------------')

    print(f'open file:{file_path}')

    with open(file_path, 'r', encoding=ENCODING_TYPE) as f:
        lines = f.readlines()

    lines_len = len(lines)
    comment_dict = {}
    template_arguments = []
    template_line_counter = 0
    template_counter = 0
    template_flg = False

    for index in range(lines_len):
        line = lines[index]
        indent = ''
        for i in range(len(line)):
            if line[i] == ' ':
                indent += ' '
            elif line[i] == '\t':
                indent += '\t'
            else:
                break

        template_line_counter = template_line_counter + 1 if template_flg else 0
        if not template_flg:
            template_arguments = []

        # templateか判定
        match = TEMPLAE_PATTERN.match(line)
        if match:
            arguments = match.group(1).split(',')
            template_arguments.extend([arg.strip() for arg in arguments])
            template_flg = True

        # クラス(構造体)か判定
        match = EXCLUDE_CLASS_PATTERN.match(line)
        if match:
            template_arguments = []
            template_flg = False
            continue

        # 最小の正規表現で一致するか判定
        match = MINIMUM_PATTERN.match(line)
        if not match:
            continue

        # 最小パターンに一致した時点で一時変数にカウントを渡し,カウンタはリセット
        # 最小パターンは,templateで使用するclass,struct,function全てに一致するため
        template_counter = template_line_counter
        template_flg = False

        # return ~();のパターンを弾く
        match = EXCLUDE_RETURN_PATTERN.match(line)
        if match:
            continue

        # const decltype(hoge)::const_iterator itr = Hoge::map.find(key);
        # のような関数定義と類似する関数呼び出しパターンを弾く
        match = EXCLUDE_IGNORE_PATTERN.match(line)
        if match:
            continue

        # void Hoge(void) = delete;
        # のようなdeleteの場合のパターンを弾く
        match = DELETE_PATTERN.match(line)
        if match:
            continue

        # 正規表現での判定
        match = FUNCTION_PATTERN.match(line)
        if not match:
            continue

        # 一行前にコメントが存在する場合は追加しない
        if '*/' in lines[index - 1 - template_counter]:
            continue

        doxygen_comment = [
            f'{indent}/**',
            f'{indent}* @fn ',
            f'{indent}* @brief ',
        ]

        # templateパラメータのコメント追加
        if template_arguments:
            doxygen_comment.extend(
                get_template_param_comment(
                    template_arguments, indent, debug_mode=debug_mode
                )
            )
            template_arguments = []

        # パラメータの判定及びコメントの追加
        doxygen_comment.extend(
            get_func_param_comment(
                line, indent=indent
            )
        )

        # 修飾子+型の判定
        modifier_and_return_type = FUNCTION_RETURN_TYPE_PATTERN.match(line)
        if modifier_and_return_type:
            return_comment = f'{indent}* @return '
            result = get_define_return_type(
                modifier_and_return_type.group(1),
                debug_mode=debug_mode
            )
            # コンストラクタの場合はコメントを追加しない
            if result == FunctionReturnType.Constructor:
                continue
            if result == FunctionReturnType.Type:
                doxygen_comment.append(return_comment)

        # コメントの追加
        doxygen_comment.append(f'{indent}*/')
        comment_dict[index - template_counter] = doxygen_comment

        if debug_mode:
            print('----line----')
            print(index)            
            print('----one line previous----')
            print(lines[index - 1], end='')
            print('----comment----')
            for t in doxygen_comment:
                print(t)
            print(line)

    # ここでコメントを追加(複雑化を防ぐために分割することにした)
    if not debug_mode:
        if not nobackup_mode:
            with open(f'{file_path}.bak','w', encoding=ENCODING_TYPE) as file:
                file.writelines(lines)

        with open(file_path, 'w', encoding=ENCODING_TYPE) as file:
            for index in range(lines_len):
                if index in comment_dict:
                    for comment in comment_dict[index]:
                        # print(comment)
                        file.writelines(f'{comment}\n')
                # print(lines[index],end='')
                file.writelines(lines[index])


def main():
    args = sys.argv
    debug_mode = '-d' in args
    test_mode = '-test' in args
    nobackup_mode = '-nobackup' in args

    if test_mode:
        test()
        return

    with open(TARGET_FILE_NAME_LIST, 'r', encoding=ENCODING_TYPE) as f:
        target_list = f.read().splitlines()

    for target in target_list:
        for extends in TARGET_FILE_EXTENDS:
            files = glob.glob(
                pathname=f'{target}/*.{extends}', recursive=True
            )
            for file_path in files:
                check_function_comment(file_path, debug_mode=debug_mode,nobackup_mode=nobackup_mode)


if __name__ == '__main__':
    main()
