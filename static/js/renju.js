/***************************************************************************************************
 *
 * Constants.
 *
 **************************************************************************************************/
var CHARACTER = {
    'EDITOR' : 'E',
    'VISITOR' : 'V'
};

var NUM_LINES = 15;

var STONE = {
    'BLACK': 'B',
    'WHITE': 'W',
    'NONE' : 'N'
};


/***************************************************************************************************
 *
 * Renju
 *
 * Public:
 *     Renju(character, upDownReflected, leftRightReflected, rotateTimes)
 *     showFreshNew()
 *     loadLibrary(libraryId, blackPlayerName, whitePlayerName, title, manual)
 *     saveLibrary()
 *     playNewMoveAt(x, y)
 *     playPassMove()
 *     deleteCurrentMove()
 *     goToBeforeFirstMove()
 *     goToPreviousFork()
 *     goToPreviousMove()
 *     goToNextMove()
 *     goToNextFork()
 *     goToLastMove()
 *     revert()
 *     reflectUpDown()
 *     reflectLeftRight()
 *     rotateClockwise()
 *     rotateCounterclockwise()
 *     searchText()
 *     searchManual()
 *
 * Private:
 *     __reinitializeMoves()
 *     __updateUi()
 *     __getSearchData(upDownReflected, leftRightReflected, rotateTimes)
 **************************************************************************************************/
function Renju(character, upDownReflected, leftRightReflected, rotateTimes) {
    this.character = character;
    this.libraryId = '';
    this.upDownReflected = upDownReflected;
    this.leftRightReflected = leftRightReflected;
    this.rotateTimes = rotateTimes;
    this.titleHtmlElement = document.getElementById('title');
    this.blackPlayerNameElement = document.getElementById('blackPlayerName');
    this.whitePlayerNameElement = document.getElementById('whitePlayerName');
    this.boardHtmlElement = document.getElementById('board');
    this.labelHtmlElement = document.getElementById('label');
    this.commentHtmlElement = document.getElementById('comment');
    if (this.character != CHARACTER.EDITOR) {
        this.titleHtmlElement.disabled = true;
        this.labelHtmlElement.disabled = true;
        this.commentHtmlElement.disabled = true;
    }
    this.rootMove = null;
    this.currentMove = null;
    this.currentBranch = null;
    this.stones = new Array(NUM_LINES);
    for (var j = 0; j < NUM_LINES; j++) {
        this.stones[j] = new Array(NUM_LINES);
    }
}

Renju.prototype.showFreshNew = function() {
    this.__reinitializeMoves();
    this.__updateUi();
}

Renju.prototype.loadLibrary = function(libraryId, title, blackPlayerName, whitePlayerName, manual) {
    this.showFreshNew();
    this.libraryId = libraryId;
    this.titleHtmlElement.value = title;
    this.blackPlayerNameElement.value = blackPlayerName;
    this.whitePlayerNameElement.value = whitePlayerName;
    manual = manual['d'];
    for (var i = 0; i < manual.length; i++) {
        new Move(this.rootMove, manual[i]);
    }
    this.goToLastMove();
}

Renju.prototype.saveLibrary = function() {
    if (this.character != CHARACTER.EDITOR) {
        return;
    }
    if (!this.currentMove.isRoot()) {
        this.currentMove.label = this.labelHtmlElement.value;
        this.currentMove.comment = this.commentHtmlElement.value;
    }
    var manual = JSON.stringify(this.rootMove.fillIn({}));
    if (manual.length > 65535) {
        alert('棋谱数据量太大!');
        return;
    }
    var apiRequest = new ApiRequest('/library/api/save');
    apiRequest.send({
                        'id':this.libraryId,
                        'title':this.titleHtmlElement.value,
                        'blackPlayerName':this.blackPlayerNameElement.value,
                        'whitePlayerName':this.whitePlayerNameElement.value,
                        'manual':manual
                    },
                    function(result) {
                        if (result['status'] != 0) {
                            return;
                        }
                        __renju__.libraryId = result['data']['id'];
                        alert('保存成功');
                    }
    );
}

Renju.prototype.playNewMoveAt = function(x, y) {
    if (x > 0 && y > 0 && this.stones[y][x] != STONE.NONE) {
        return;
    }
    var parent = this.currentMove;
    var manual = {'x': x, 'y': y, 'm': 1, 'l':'', 'c':'', 'd':[]};
    var newMove = new Move(parent, manual);
    newMove.play();
}

Renju.prototype.playPassMove = function() {
    this.playNewMoveAt(-1, -1);
}

Renju.prototype.deleteCurrentMove = function() {
    if (!this.currentMove.isRoot()) {
        var toDelete = this.currentMove;
        this.goToPreviousMove();
        toDelete.__hide();
        var siblings = this.currentMove.descendants;
        var index = -1;
        for (var i = 0; i < siblings.length; i++) {
            if (siblings[i] == toDelete) {
                index = i;
            }
        }
        delete siblings[index];
        siblings.splice(index, 1);
    } else {
        var descendants = this.currentMove.descendants;
        for (var i = 0; i < descendants.length; i++) {
            var descendant = descendants[i];
            descendant.__hide();
            delete descendant;
        }
        this.currentMove.descendants = new Array();
    }
}

Renju.prototype.goToBeforeFirstMove = function() {
    while (!this.currentMove.isRoot()) {
        this.currentMove.recall();
    }
}

Renju.prototype.goToPreviousFork = function() {
    while (!this.currentMove.isRoot()) {
        this.currentMove.recall();
        if (this.currentMove.descendants.length > 1) {
            return;
        }
    }
}

Renju.prototype.goToPreviousMove = function() {
    if (!this.currentMove.isRoot()) {
        this.currentMove.recall();
    }
}

Renju.prototype.goToNextMove = function() {
    var descendants = this.currentMove.descendants;
    for (var i = 0; i < descendants.length; i++) {
        if (descendants[i].isMajor) {
            descendants[i].play();
            return;
        }
    }
}

Renju.prototype.goToNextFork = function() {
    while (true) {
        var currentMove = this.currentMove;
        var descendants = currentMove.descendants;
        if (descendants.length != 1) {
            return;
        }
        descendants[0].play();
    }
}

Renju.prototype.goToLastMove = function() {
    while (true) {
        var lastMoveFound = true;
        var currentMove = this.currentMove;
        var descendants = currentMove.descendants;
        for (var i = 0; i < descendants.length; i++) {
            if (descendants[i].isMajor) {
                descendants[i].play();
                lastMoveFound = false;
                break;
            }
        }
        if (lastMoveFound) {
            return;
        }
    }
}

Renju.prototype.revert = function() {
    this.upDownReflected = false;
    this.leftRightReflected = false;
    this.rotateTimes = 0;
    this.__updateUi();
}

Renju.prototype.reflectUpDown = function() {
    this.upDownReflected = !this.upDownReflected;
    this.__updateUi();
}

Renju.prototype.reflectLeftRight = function() {
    this.leftRightReflected = !this.leftRightReflected;
    this.__updateUi();
}

Renju.prototype.rotateClockwise = function() {
    if (this.upDownReflected ^ this.leftRightReflected) {
        this.rotateTimes += 3;
    } else {
        this.rotateTimes += 1;
    }
    this.__updateUi();
}

Renju.prototype.rotateCounterclockwise = function() {
    if (this.upDownReflected ^ this.leftRightReflected) {
        this.rotateTimes += 1;
    } else {
        this.rotateTimes += 3;
    }
    this.__updateUi();
}

Renju.prototype.searchText = function() {
    if (this.titleHtmlElement.value.length == 0) {
        return;
    }
    var keyword = this.titleHtmlElement.value;
    var formRequest = new FormRequest('/library/searchText', 'post', '_self');
    formRequest.send({
                         'keyword':keyword,
                         'page':0
                     });
}

Renju.prototype.searchManual = function() {
    if (this.currentBranch.length <= 1) {
        return;
    }
    var numMoves = Math.min(30, this.currentBranch.length - 1);
    var searchDatas = new Array();
    searchDatas.push(this.__getSearchData(false, false, 0));
    searchDatas.push(this.__getSearchData(true, false, 1));
    searchDatas.push(this.__getSearchData(false, false, 3));
    searchDatas.push(this.__getSearchData(true, false, 0));
    searchDatas.push(this.__getSearchData(true, true, 0));
    searchDatas.push(this.__getSearchData(false, true, 1));
    searchDatas.push(this.__getSearchData(false, false, 1));
    searchDatas.push(this.__getSearchData(false, true, 0));
    searchDatas.sort();
    var last = searchDatas[0];
    for (var i = 1; i < searchDatas.length; i++) {
        if (last == searchDatas[i]) {
            searchDatas.splice(i--, 1);
        } else {
            last = searchDatas[i];
        }
    }
    var formRequest = new FormRequest('/library/searchManual', 'post', '_self');
    formRequest.send({
                         'searchDatas':JSON.stringify(searchDatas),
                         'page':0
                     });
}

Renju.prototype.__reinitializeMoves = function() {
    var manual = {'x': -1, 'y': -1, 'm': 1, 'l': '', 'c': '', 'd': []};
    this.rootMove = new Move(null, manual);
    this.currentMove = this.rootMove;
    this.currentBranch = new Array();
    this.currentBranch.push(this.rootMove);
    for (var j = 0; j < NUM_LINES; j++) {
        for (var i = 0; i < NUM_LINES; i++) {
            this.stones[j][i] = STONE.NONE;
        }
    }
}

Renju.prototype.__updateUi = function() {
    var boardInnerHtml = '<table class="board" background="/static/img/board.png" border="0" cellspacing="0" cellpadding="0">';
    for (var j = NUM_LINES - 1; j >= -1; j--) {
        boardInnerHtml += '<tr>';
        for (var i = -1; i < NUM_LINES; i++) {
            var x = i;
            var y = j;
            if (this.upDownReflected) {
                y = NUM_LINES - 1 - y;
            }
            if (this.leftRightReflected) {
                x = NUM_LINES - 1 - x;
            }
            for (var k = 0; k < this.rotateTimes % 4; k++) {
                x = x ^ y;
                y = x ^ y;
                x = x ^ y;
                x = NUM_LINES - 1 - x;
            }
            if (i == -1 && j == -1) {
                boardInnerHtml += '<td class="boardLabel">&nbsp;</td>';
            } else if (i == -1) {
                boardInnerHtml += '<td class="boardLabel">' + (j + 1) + '</td>';
            } else if (j == -1) {
                boardInnerHtml += '<td class="boardLabel">' + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.charAt(i) + '</td>';
            } else {
                boardInnerHtml += '<td class="boardSpot" id="i_' + x + '_' + y + '" onclick="__renju__.playNewMoveAt(' + x + ', ' + y + ');" onselectstart="return false;">&nbsp;</td>';
            }
        }
        boardInnerHtml += '</tr>';
    }
    boardInnerHtml += '</table>';
    this.boardHtmlElement.innerHTML = boardInnerHtml;
    var lastMove = null;
    for (var i = 0; i < this.currentBranch.length; i++) {
        lastMove = this.currentBranch[i];
        lastMove.replay();
    }
}

Renju.prototype.__getSearchData = function(upDownReflected, leftRightReflected, rotateTimes) {
    var part1 = new Array();
    var part2 = new Array();
    for (var i = 1; i < Math.min(31, this.currentBranch.length); i++) {
    var currentBranch = this.currentBranch[i];
        var x = currentBranch.x;
        var y = currentBranch.y;
        if (upDownReflected) {
            y = NUM_LINES - 1 - y;
        }
        if (leftRightReflected) {
            x = NUM_LINES - 1 - x;
        }
        for (var j = 0; j < rotateTimes % 4; j++) {
            x = x ^ y;
            y = x ^ y;
            x = x ^ y;
            x = NUM_LINES - 1 - x;
        }
        if (i % 2 == 1) {
            part1.push('|' + x + '_' + y);
        } else {
            part2.push('|' + x + '_' + y);
        }
    }
    part1.sort();
    part2.sort();
    return part1.join('') + part2.join('');
}


/***************************************************************************************************
 *
 * Move
 *
 * Public:
 *     Move(parent, manual)
 *     fillIn(manual)
 *     play()
 *     replay()
 *     recall()
 *     isRoot()
 *
 * Private:
 *     __play()
 *     __markAsMajor()
 *     __markAsVariant()
 *     __showAsMajor()
 *     __showAsLast()
 *     __showAsVariant()
 *     __hide()
 *     __isPass()
 *     __getHtmlElement()
 **************************************************************************************************/
function Move(parent, manual) {
    this.parent = parent;
    this.x = manual['x'];
    this.y = manual['y'];
    this.index = (parent != null) ? (parent.index + 1) : 0;
    this.stone = (this.index % 2 == 1 ? STONE.BLACK : STONE.WHITE);
    this.isMajor = (manual['m'] == 1);
    this.label = manual['l'];
    this.comment = manual['c'];
    manual = manual['d'];
    this.descendants = new Array();
    for (var i = 0; i < manual.length; i++) {
        new Move(this, manual[i]);
    }
    if (parent != null) {
        parent.descendants.push(this);
    }
}

Move.prototype.fillIn = function(manual) {
    manual['x'] = this.x;
    manual['y'] = this.y;
    manual['m'] = this.isMajor ? 1 : 0;
    manual['l'] = this.label;
    manual['c'] = this.comment;
    manual['d'] = new Array();
    for (var i = 0; i < this.descendants.length; i++) {
        manual['d'].push(this.descendants[i].fillIn({}));
    }
    return manual;
}

Move.prototype.play = function() {
    __renju__.currentBranch.push(this);
    if (!this.__isPass()) {
        __renju__.stones[this.y][this.x] = this.stone;
    }
    if (this.__isPass() && !this.isRoot()) {
        document.getElementById('pass').style.visibility = 'visible';
        setTimeout('document.getElementById("pass").style.visibility="hidden"', 1000);
    }
    __renju__.currentMove = this;
    var parent = this.parent;
    parent.label = __renju__.labelHtmlElement.value;
    parent.comment = __renju__.commentHtmlElement.value;
    this.__play();
}

Move.prototype.replay = function() {
    this.__play();
}

Move.prototype.recall = function() {
    if (this.isRoot()) {
        return;
    }
    this.label = __renju__.labelHtmlElement.value;
    this.comment = __renju__.commentHtmlElement.value;
    __renju__.currentBranch.pop();
    __renju__.currentMove = this.parent;
    if (!this.__isPass()) {
        __renju__.stones[this.y][this.x] = STONE.NONE;
    }
    var descendants = this.descendants;
    for (var i = 0; i < descendants.length; i++) {
        descendants[i].__hide();
    }
    var siblings = this.parent.descendants;
    for (var i = 0; i < siblings.length; i++) {
        siblings[i].__showAsVariant();
    }
    this.parent.__showAsLast();
}

Move.prototype.isRoot = function() {
    return this.parent == null;
}

Move.prototype.__play = function() {
    var parent = this.parent;
    if (parent != null) {
        var siblings = parent.descendants;
        for (var i = 0; i < siblings.length; i++) {
            var sibling = siblings[i];
            if (sibling != this) {
                sibling.__markAsVariant();
                sibling.__hide();
            }
        }
        parent.__showAsMajor();
        this.__markAsMajor();
        this.__showAsLast();
    }
    for (var i = 0; i < this.descendants.length; i++) {
        this.descendants[i].__showAsVariant();
    }
}

Move.prototype.__markAsMajor = function() {
    this.isMajor = true;
}

Move.prototype.__markAsVariant = function() {
    this.isMajor = false;
    for (var i = 0; i < this.descendants.length; i++) {
        this.descendants[i].__markAsVariant();
    }
}

Move.prototype.__showAsMajor = function() {
    if (!this.__isPass()) {
        var htmlElement = this.__getHtmlElement();
        htmlElement.innerHTML = this.index;
        htmlElement.style.color = (this.stone == STONE.BLACK ? '#ffffff' : '000000')
        htmlElement.style.backgroundImage = (this.stone == STONE.BLACK ? 'url(/static/img/black_stone.png)' : 'url(/static/img/white_stone.png)');
        htmlElement.onclick = function() {
            return;
        };
    }
}

Move.prototype.__showAsLast = function() {
    if (!this.__isPass()) {
        var htmlElement = this.__getHtmlElement();
        htmlElement.innerHTML = this.index;
        htmlElement.style.color = '#ff0000';
        htmlElement.style.backgroundImage = (this.stone == STONE.BLACK ? 'url(/static/img/black_stone.png)' : 'url(/static/img/white_stone.png)');
        htmlElement.onclick = function() {
            return;
        };
    }
    __renju__.labelHtmlElement.value = this.label;
    __renju__.commentHtmlElement.value = this.comment;
}

Move.prototype.__showAsVariant = function() {
    if (this.__isPass()) {
        return;
    }
    var htmlElement = this.__getHtmlElement();
    if (this.label == '') {
        if (this.stone == STONE.BLACK) {
            htmlElement.innerHTML = '&nbsp;';
            htmlElement.style.color = '#ffffff';
            htmlElement.style.backgroundImage = 'url(/static/img/black_variant.png)';
        } else {
            htmlElement.innerHTML = '&nbsp;';
            htmlElement.style.color = '#000000';
            htmlElement.style.backgroundImage = 'url(/static/img/white_variant.png)';
        }
    } else {
        htmlElement.innerHTML = this.label;
        htmlElement.style.color = '#000000';
        htmlElement.style.backgroundImage = 'url(/static/img/block.png)';
    }
    var currentMove = this;
    htmlElement.onclick = function() {
        currentMove.play();
    }
}

Move.prototype.__hide = function() {
    if (this.__isPass()) {
        return;
    }
    var _x = this.x;
    var _y = this.y;
    var htmlElement = this.__getHtmlElement();
    htmlElement.innerHTML = '&nbsp;';
    htmlElement.style.backgroundImage = 'url(/static/img/none.png)';
    htmlElement.onclick = function() {
        __renju__.playNewMoveAt(_x, _y);
    };
}

Move.prototype.__isPass = function() {
    return this.x < 0 || this.y < 0;
}

Move.prototype.__getHtmlElement = function() {
    return document.getElementById('i_' + this.x + '_' + this.y);
}
