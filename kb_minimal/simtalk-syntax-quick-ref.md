# SimTalk 2.0 Syntax Quick Reference

A self-authored cheat sheet of the SimTalk 2.0 language surface most commonly used in day-to-day modelling. This file does **not** reproduce Siemens documentation; for authoritative behaviour, consult your licensed Plant Simulation Help.

## Comments

```simtalk
-- single line comment (to end of line)
/* multi-line
   comment */
```

Note: `-->` is NOT a comment — it's a visual arrow in documentation.

## Declarations

```simtalk
var name : type                    -- local variable (method scope)
local name : type                  -- same as var
param name : type                  -- input parameter
result : type                      -- return type declaration (in method signature)
var name : type := initialValue    -- declaration with initialization
var a, b, c : integer              -- multiple declarations (same type)
```

### Common Types
`integer`, `real`, `boolean`, `string`, `object`, `table`, `any`, `void`
Arrays: `integer[3]`, `string[10]`, `real[,]` (2D)

## Assignment & Operators

```simtalk
name := value          -- assignment
name += value          -- increment
name -= value          -- decrement
```

### Comparison
`=`, `/=` (not equal), `<`, `>`, `<=`, `>=`

### Logical
`and`, `or`, `not`

### String
`+` (concatenation), `strLPos(haystack, needle)`, `strRPos(...)`, `strCopy(...)`, `num_to_str(...)`, `str_to_num(...)`

## Control Flow

### If-Then-Else
```simtalk
if condition
    -- block (indented)
elseif condition
    -- block
else
    -- block
end
```

### For Loop
```simtalk
for var i := 1 to upperBound
    -- block
next

for var i := upperBound downto 1
    -- block
next
```

### While Loop
```simtalk
while condition
loop
    -- block (indented inside loop)
end
```

### Repeat-Until
```simtalk
repeat
    -- block
until condition
```

### Switch-Case
```simtalk
switch expression
case value1:
    -- block
case value2:
    -- block
default:
    -- block
end
```

## Indentation Rules

| Keyword | Effect |
|---------|--------|
| `if`, `for`, `while`, `repeat`, `switch` | Next line +1 indent |
| `loop` (after `while`) | Same level as `while`, content +1 |
| `case`, `default` | Close previous case (-1), open new (+1) |
| `elseif`, `else` | Close previous block (-1), open new (+1) |
| `end`, `next`, `until` | Close block (-1 on this line) |

Indent unit: **tab** (Plant Simulation convention).

## Object References & Paths

```simtalk
self                    -- current method's owner object
self.~                  -- parent frame of the method's object
root                    -- model root
@.                      -- MU that triggered the entrance/exit control
?.                      -- object (or Method) that called the current Method
```

### Path navigation
```simtalk
root.Models.Frame1.Station1          -- absolute path
self.~.Buffer1                       -- relative to parent
@.Name                               -- attribute of the triggering MU
?.Cont.move(E2)                      -- move MU from the calling object
```

## Method Calls

```simtalk
object.methodName(arg1, arg2)        -- call method on object
result := object.methodName(...)     -- capture return value
object.methodName                    -- no-arg call (parentheses optional)
```

## Common Patterns

### Table Access
```simtalk
table[columnName, row]               -- cell by column name + row index
table[colIndex, row]                 -- cell by column index + row index
table.xDim                           -- number of columns
table.yDim                           -- number of rows
```

### MU (Moving Unit) Operations
```simtalk
@.move(destination)                  -- move MU to destination
Station.Cont                         -- access the MU on the station
.MUs.Part.create(destination)        -- create new MU instance at destination
@.delete                             -- destroy the triggering MU
```

### Event Controls
```simtalk
-- Common sensor controls:
-- init, reset, exitControl, entranceControl, endSim
-- Method signature for entrance/exit:
param mu : object -> void            -- or -> object for routing
```

### Wait / Pause
```simtalk
waituntil condition prio priority
self.operationTime := timeValue
self.startPause / self.stopPause
```

## Built-in Functions Quick Reference

### Date/Time Conversion

| Function | Signature | Description |
|----------|-----------|-------------|
| `datetime_to_str` | `(Value:datetime[, Format:string]) → string` | DateTime to formatted string. Format: `%Y`(4-digit year), `%y`(2-digit), `%m`(month 01-12), `%d`(day 01-31), `%H`(hour 00-23), `%h`(12h), `%M`(min), `%S`(sec int), `%s`(sec real), `%p`(am/pm), `%P`(AM/PM) |
| `time_to_str` | `(Value:time[, FormatLikeDialogs:boolean]) → string` | Time (elapsed) to string. `false`/omit=table format (4 decimals), `true`=dialog format. Both include decimals; use `strLPos`+`strCopy` to truncate |
| `str_to_time` | `(Value:string) → time` | Parse string to time |
| `str_to_date` | `(Value:string) → date` | Parse string to date (locale-dependent) |
| `str_to_datetime` | `(Value:string) → datetime` | Parse string to datetime (locale-dependent) |

**`datetime_to_str` examples:**
```simtalk
datetime_to_str(root.EventController.AbsSimTime, "%Y-%m-%d %H:%M:%S")  -- "2025-10-20 20:50:40"
datetime_to_str(sysDate, "%d.%m.%y %H:%M:%S")                          -- "20.03.18 0:43:22"
```

### Date/Time Extraction

| Function | Signature | Description |
|----------|-----------|-------------|
| `day` | `(Date/DateTime) → integer` | Day of month |
| `month` | `(Date/DateTime) → integer` | Month (1-12) |
| `year` | `(Date/DateTime) → integer` | Years since 1900 |
| `CalendarYear` | `(DateTime) → integer` | Full calendar year (e.g. 2025) |
| `timeOfDay` | `(DateTime) → time` | Time portion |
| `getDate` | `(DateTime) → date` | Date portion |
| `dayOfWeek` | `(Date/DateTime) → integer` | 0=Sun, 1=Mon … 6=Sat |
| `CalendarWeek` | `(DateTime) → integer` | ISO 8601 calendar week |
| `sysDate` | `→ datetime` | Current system clock |

### Type Conversion

| Function | Signature | Description |
|----------|-----------|-------------|
| `to_str` | `(any[, any, …]) → string` | Convert/concatenate any values to string |
| `num_to_str` | `(Number:real[, Precision:integer, Width:integer]) → string` | Number to string. Negative precision = total width includes decimals |
| `str_to_num` | `(Value:string) → real` | Parse numeric string (supports hex `0x`) |
| `obj_to_str` | `(obj:object[, MakeAbsolute:boolean:=true]) → string` | Object path to string |
| `str_to_obj` | `(Value:string) → object` | String path to object reference |
| `bool_to_num` | `(Value:boolean) → integer` | true→1, false→0 |
| `num_to_bool` | `(Value:real) → boolean` | 0→false, else→true |
| `time_to_num` | `(Data:time) → real` | Time to seconds (real) |
| `length_to_num` | `(Data:length[, Unit:string="m"]) → real` | Length to number with unit |
| `speed_to_num` | `(Data:speed[, Unit:string="m/s"]) → real` | Speed to number with unit |

### Math Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `ceil` | `(x:real) → integer` | Smallest integer ≥ x |
| `floor` | `(x:real) → integer` | Greatest integer ≤ x |
| `round` | `(x:real[, places:integer]) → real/integer` | Round; no places→nearest int, with places→decimal |
| `max` | `(x, y[, z, …]) → same type` | Maximum (supports >2 args; numeric, date, or string) |
| `min` | `(x, y[, z, …]) → same type` | Minimum (same rules as max) |
| `abs` | `(x:real) → real` | Absolute value |
| `mod` | `(a:integer, b:integer) → integer` | Modulo |
| `sqrt` | `(x:real) → real` | Square root |
| `pi` | constant `real` | 3.14159… |

### String Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `strLen` | `(Text:string) → integer` | String length |
| `strLPos` | `(haystack, needle:string) → integer` | Find from left (0=not found) |
| `strRPos` | `(haystack, needle:string) → integer` | Find from right |
| `strCopy` | `(s:string, start:integer, length:integer) → string` | Substring |

### Output & Dialog

| Function | Signature | Description |
|----------|-----------|-------------|
| `print` | `(any)` | Output to console |
| `messageBox` | `(Text:string[, Buttons:integer, Symbol:integer]) → integer` | Show dialog; returns button clicked |

## Statement Boundary Signals (for code parsing)

These patterns reliably indicate where one statement ends and another begins:
1. `--` comment marker (unless `-->` arrow)
2. `:=` / `+=` / `-=` assignment operators
3. `var`/`local`/`param`/`result` declarations
4. Control flow openers: `if`, `for`, `while`, `repeat`, `switch` (with syntax validation)
5. Control flow closers: `end`, `next`, `until`
6. `return` keyword
7. `.methodName(...)` chains starting a new expression
