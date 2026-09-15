class lol.gpui.HintManager extends lol.gpui.GPUIObject
{
   var hintArr;
   var prevLink;
   static var hintLayer;
   static var hint_mc;
   static var t1;
   static var t2;
   static var TIME_PAUSE = 500;
   var F1 = false;
   var buildArr = false;
   static var hintWasShow = false;
   static var FIRST_HINT_PAUSE = 1000;
   static var OTHER_HINT_PAUS = 200;
   static var EXIT_LOC = "exitLoc_btn";
   static var EQUIPMENT = "equipment";
   static var PERS_INFO = "persInfo";
   static var EQUIPMENT1 = "equipment1";
   static var PERS_INFO1 = "persInfo1";
   static var QUEST = "quest";
   static var QUEST1 = "quest1";
   static var CLAN = "clan";
   static var SETTINGS = "settings";
   static var COPY_LOG = "copyLog";
   static var COPY_HASH = "copyHash";
   static var MAIL = "mail";
   static var RELOAD = "reload_btn";
   static var GOLD = "GOLD";
   static var FIRE_MODE_0 = "fireMod0";
   static var FIRE_MODE_1 = "fireMod1";
   static var FIRE_MODE_2 = "fireMod2";
   static var HEALTH_BAR = "healthBar";
   static var STAMINA_BAR = "staminaBar";
   static var HEALTH_COUNT = "healthCount";
   static var STAMINA_COUNT = "staminaCount";
   static var MINI_MAP = "miniMap";
   static var OC_MINI_MAP = "openCloseMM";
   static var OC_WEAPON_PAN = "openCloseWeaponPan";
   static var CHANGE_SLOT = "changeSlot";
   static var GOLD_TO_AFRO = "goldToAfro";
   static var ADD_GOLD = "addGold";
   static var HELP = "help";
   static var FILTER_0 = "filter0";
   static var FILTER_1 = "filter1";
   static var FILTER_2 = "filter2";
   static var FILTER_3 = "filter3";
   static var FILTER_4 = "filter4";
   static var FILTER_5 = "filter5";
   static var ICON_BTN = "icon_btn";
   static var LIST_BTN = "list_btn";
   static var ENTER_LOC = "enterLoc";
   static var CENTER_TO_CHAR = "centerToChar";
   static var OON_OFF_GRID = "grid";
   static var SCALE_UP = "scaleUp";
   static var SCALE_DOWN = "scaleDown";
   static var CREATE_LABEL = "createLabel";
   static var CENTER_TO_LABEL = "centerToLabel";
   static var MOVE_TO_LABEL = "moveToLabel";
   static var SOHW_HIDE_LABELS = "labels";
   static var EDIT_LABEL = "editLabel";
   static var USERS_LIST = "userList";
   static var LABELS_LIST = "labelList";
   static var OC_LABEL_PAN = "labelPan";
   static var OC_MOVE_PAN = "movePan";
   static var FOLLOW_TO_PLAYER = "followToPlayer";
   static var SEND_MESSAGE = "sendMessage";
   static var BG0 = "bg0";
   static var BG1 = "bg1";
   static var BG2 = "bg2";
   static var BG3 = "bg3";
   static var BG4 = "bg4";
   static var BG5 = "bg5";
   static var BG6 = "bg6";
   static var BG7 = "bg7";
   static var BG8 = "bg8";
   static var BG9 = "bg9";
   static var BG10 = "bg10";
   static var BG11 = "bg11";
   static var BG12 = "bg12";
   static var BG13 = "bg13";
   static var BG14 = "bg14";
   static var SKILL_BG0 = "skill_bg0";
   static var SKILL_BG1 = "skill_bg1";
   static var SKILL_BG2 = "skill_bg2";
   static var SKILL_BG3 = "skill_bg3";
   static var SKILL_BG4 = "skill_bg4";
   static var ACTION_POINT = "action_point";
   static var SHOW_TIME = "showTime";
   static var CLEAR_CHAT = "clearChat";
   static var STAMINA_HEALTH_BAR = "staminaHealthBar";
   static var HEAL = "heal";
   static var EAT = "eat";
   static var FORUM = "forum";
   var keyD = false;
   function HintManager()
   {
      super();
      lol.gpui.HintManager.hintLayer = lol.core.SceneShifter.linkHint;
      Key.addListener(this);
      this.createHintArr();
   }
   static function showHint(str, topShift, bottomShift, X, Y)
   {
      lol.gpui.HintManager.closeHint();
      if(!lol.gpui.HintManager.hintWasShow)
      {
         lol.gpui.HintManager.t1 = new lol.utils.Timeout(lol.gpui.HintManager,lol.gpui.HintManager._showHint,lol.gpui.HintManager.FIRST_HINT_PAUSE,str,topShift,bottomShift,X,Y);
      }
      else
      {
         lol.gpui.HintManager._showHint(str,topShift,bottomShift,X,Y);
      }
   }
   static function _showHint(str, topShift, bottomShift, X, Y)
   {
      lol.gpui.HintManager.t2.Clear();
      lol.gpui.HintManager.hint_mc = lol.gpui.HintManager.hintLayer.attachMovie("hintMC","hintMC",lol.gpui.HintManager.hintLayer.getNextHighestDepth());
      lol.gpui.HintManager.hint_mc.title_str = str;
      lol.gpui.HintManager.hint_mc._x = !X ? lol.gpui.HintManager.hintLayer._xmouse : X;
      lol.gpui.HintManager.hint_mc._y = !Y ? lol.gpui.HintManager.hintLayer._ymouse : Y;
      lol.gpui.HintManager.hintWasShow = true;
      if(!X && !Y)
      {
         lol.gpui.HintManager.hint_mc.onMouseMove = lol.gpui.HintManager.checkPosition;
      }
   }
   static function checkPosition()
   {
      lol.gpui.HintManager.hint_mc._x = lol.gpui.HintManager.hintLayer._xmouse;
      lol.gpui.HintManager.hint_mc._y = lol.gpui.HintManager.hintLayer._ymouse;
   }
   static function closeHint()
   {
      lol.gpui.HintManager.t1.Clear();
      lol.gpui.HintManager.t2 = new lol.utils.Timeout(lol.gpui.HintManager,lol.gpui.HintManager.hintWasShow_func,lol.gpui.HintManager.OTHER_HINT_PAUS);
      delete lol.gpui.HintManager.hint_mc.onMouseMove;
      lol.gpui.HintManager.hint_mc.removeHint();
   }
   static function hintWasShow_func()
   {
      lol.gpui.HintManager.hintWasShow = false;
   }
   function createHintArr()
   {
      this.hintArr = new Array();
      this.hintArr[lol.gpui.HintManager.EXIT_LOC] = {text:"Перейти на глобальную карту/в локацию",hotKey:lol.services.HotKeyEvent.CHANGE_WORLD};
      this.hintArr[lol.gpui.HintManager.EQUIPMENT] = {text:"Инвентарь",hotKey:lol.services.HotKeyEvent.EQUIPMENT};
      this.hintArr[lol.gpui.HintManager.PERS_INFO] = {text:"Информация о персонаже",hotKey:lol.services.HotKeyEvent.PERS_INFO};
      this.hintArr[lol.gpui.HintManager.EQUIPMENT1] = {text:"Инвентарь",hotKey:lol.services.HotKeyEvent.EQUIPMENT};
      this.hintArr[lol.gpui.HintManager.PERS_INFO1] = {text:"Информация о персонаже",hotKey:lol.services.HotKeyEvent.PERS_INFO};
      this.hintArr[lol.gpui.HintManager.CLAN] = {text:"Клан"};
      this.hintArr[lol.gpui.HintManager.QUEST] = {text:"Задания"};
      this.hintArr[lol.gpui.HintManager.QUEST1] = {text:"Задания"};
      this.hintArr[lol.gpui.HintManager.SETTINGS] = {text:"Игровые настройки",hotKey:lol.services.HotKeyEvent.SETTINGS};
      this.hintArr[lol.gpui.HintManager.COPY_LOG] = {text:"Копировать лог в буфер обмена",hotKey:lol.services.HotKeyEvent.COPY_LOG};
      this.hintArr[lol.gpui.HintManager.COPY_HASH] = {text:"Копировать хэш в буфер обмена"};
      this.hintArr[lol.gpui.HintManager.MAIL] = {text:"Почта"};
      this.hintArr[lol.gpui.HintManager.RELOAD] = {text:"Перезарядка",hotKey:lol.services.HotKeyEvent.RELOAD};
      this.hintArr[lol.gpui.HintManager.GOLD] = {text:"Добавить денег"};
      this.hintArr[lol.gpui.HintManager.FIRE_MODE_0] = {text:"Режимы стрельбы"};
      this.hintArr[lol.gpui.HintManager.FIRE_MODE_1] = {text:"Режимы стрельбы"};
      this.hintArr[lol.gpui.HintManager.FIRE_MODE_2] = {text:"Режимы стрельбы"};
      this.hintArr[lol.gpui.HintManager.HEALTH_BAR] = {text:"Индикатор здоровья"};
      this.hintArr[lol.gpui.HintManager.STAMINA_BAR] = {text:"Индикатор выносливости"};
      this.hintArr[lol.gpui.HintManager.HEALTH_COUNT] = {text:"Счетчик здоровья"};
      this.hintArr[lol.gpui.HintManager.STAMINA_COUNT] = {text:"Счетчик выносливости"};
      this.hintArr[lol.gpui.HintManager.MINI_MAP] = {text:"Миникарта",hotKey:lol.services.HotKeyEvent.MINI_MAP};
      this.hintArr[lol.gpui.HintManager.OC_MINI_MAP] = {text:"Открыть/закрыть миникарту",hotKey:lol.services.HotKeyEvent.MINI_MAP};
      this.hintArr[lol.gpui.HintManager.OC_WEAPON_PAN] = {text:"Открыть/закрыть оружейную панель",hotKey:lol.services.HotKeyEvent.WEAPON_PAN};
      this.hintArr[lol.gpui.HintManager.CHANGE_SLOT] = {text:"Сменить активный слот",hotKey:lol.services.HotKeyEvent.CHANGE_WEAPON};
      this.hintArr[lol.gpui.HintManager.SHOW_TIME] = {text:"Показывать время сообщений"};
      this.hintArr[lol.gpui.HintManager.CLEAR_CHAT] = {text:"Очистить поле сообщений"};
      this.hintArr[lol.gpui.HintManager.FILTER_0] = {text:"Фильтровать по оружию",hotKey:lol.services.HotKeyEvent.FILTER0};
      this.hintArr[lol.gpui.HintManager.FILTER_1] = {text:"Фильтровать по одежде",hotKey:lol.services.HotKeyEvent.FILTER1};
      this.hintArr[lol.gpui.HintManager.FILTER_2] = {text:"Фильтровать по восстанавливающим средствам",hotKey:lol.services.HotKeyEvent.FILTER2};
      this.hintArr[lol.gpui.HintManager.FILTER_3] = {text:"Фильтровать по патронам",hotKey:lol.services.HotKeyEvent.FILTER3};
      this.hintArr[lol.gpui.HintManager.FILTER_4] = {text:"Фильтровать по остальным предметам",hotKey:lol.services.HotKeyEvent.FILTER4};
      this.hintArr[lol.gpui.HintManager.FILTER_5] = {text:"Фильтровать по холодному оружию",hotKey:lol.services.HotKeyEvent.FILTER5};
      this.hintArr[lol.gpui.HintManager.ICON_BTN] = {text:"Вид с изображением предмета"};
      this.hintArr[lol.gpui.HintManager.LIST_BTN] = {text:"Вид без изображения предмета"};
      this.hintArr[lol.gpui.HintManager.STAMINA_HEALTH_BAR] = {text:"Это индикатор здоровья и выносливости"};
      this.hintArr[lol.gpui.HintManager.GOLD_TO_AFRO] = {text:"Обмен золота на афро"};
      this.hintArr[lol.gpui.HintManager.ADD_GOLD] = {text:"Пополнить счет"};
      this.hintArr[lol.gpui.HintManager.HELP] = {text:"Помощь"};
      this.hintArr[lol.gpui.HintManager.HEAL] = {text:"Восстановить здоровье",hotKey:lol.services.HotKeyEvent.HEAL};
      this.hintArr[lol.gpui.HintManager.EAT] = {text:"Восстановить силы",hotKey:lol.services.HotKeyEvent.EAT};
      this.hintArr[lol.gpui.HintManager.FORUM] = {text:"Перейти на форум"};
      this.hintArr[lol.gpui.HintManager.ENTER_LOC] = {text:"Перейти в локацию",hotKey:lol.services.HotKeyEvent.CHANGE_WORLD};
      this.hintArr[lol.gpui.HintManager.CENTER_TO_CHAR] = {text:"Центровать на персонаже",hotKey:lol.services.HotKeyEvent.CENTER_ON_CHAR};
      this.hintArr[lol.gpui.HintManager.OON_OFF_GRID] = {text:"Включить/выключить сетку",hotKey:lol.services.HotKeyEvent.GRID};
      this.hintArr[lol.gpui.HintManager.SCALE_UP] = {text:"Увеличить масштаб",hotKey:lol.services.HotKeyEvent.SCALE_UP};
      this.hintArr[lol.gpui.HintManager.SCALE_DOWN] = {text:"Уменьшить масштаб",hotKey:lol.services.HotKeyEvent.SCALE_DOWN};
      this.hintArr[lol.gpui.HintManager.CREATE_LABEL] = {text:"Создать метку на карте"};
      this.hintArr[lol.gpui.HintManager.CENTER_TO_LABEL] = {text:"Центровать на метке"};
      this.hintArr[lol.gpui.HintManager.MOVE_TO_LABEL] = {text:"Идти к метке"};
      this.hintArr[lol.gpui.HintManager.SOHW_HIDE_LABELS] = {text:"Показать/скрыть метки на карте"};
      this.hintArr[lol.gpui.HintManager.EDIT_LABEL] = {text:"Редактировать метку"};
      this.hintArr[lol.gpui.HintManager.USERS_LIST] = {text:"Список игроков"};
      this.hintArr[lol.gpui.HintManager.LABELS_LIST] = {text:"Список меток на карте"};
      this.hintArr[lol.gpui.HintManager.OC_LABEL_PAN] = {text:"Открыть/закрыть панель меток и списка игроков"};
      this.hintArr[lol.gpui.HintManager.OC_MOVE_PAN] = {text:"Открыть/закрыть панель движения"};
      this.hintArr[lol.gpui.HintManager.FOLLOW_TO_PLAYER] = {text:"Перехват игрока"};
      this.hintArr[lol.gpui.HintManager.SEND_MESSAGE] = {text:"Отправить сообщение (Enter)"};
      this.hintArr[lol.gpui.HintManager.BG0] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG1] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG2] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG3] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG4] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG5] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG6] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG7] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG8] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG9] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG10] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG11] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG12] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG13] = {text:""};
      this.hintArr[lol.gpui.HintManager.BG14] = {text:""};
      this.hintArr[lol.gpui.HintManager.SKILL_BG0] = {text:""};
      this.hintArr[lol.gpui.HintManager.SKILL_BG1] = {text:""};
      this.hintArr[lol.gpui.HintManager.SKILL_BG2] = {text:""};
      this.hintArr[lol.gpui.HintManager.SKILL_BG3] = {text:""};
      this.hintArr[lol.gpui.HintManager.SKILL_BG4] = {text:""};
      this.hintArr[lol.gpui.HintManager.ACTION_POINT] = {text:""};
   }
   function addHint(instance, mov, hint_str, folowMouse)
   {
      if(hint_str)
      {
         this.hintArr[instance].text = hint_str;
      }
      if(!this.hintArr[instance].mc)
      {
         mov.hintInstance = instance;
         this.hintArr[instance].mc = mov;
         mov.addEventListener(lol.gpui.controls.GPUIButton.SHOW_HINT,this);
         mov.addEventListener(lol.gpui.controls.GPUIButton.REMOVE_HINT,this);
      }
      else if(this.hintArr[instance].mc == mov)
      {
         this.hintArr[instance].mc.removeEventListener(lol.gpui.controls.GPUIButton.SHOW_HINT,this);
         this.hintArr[instance].mc.removeEventListener(lol.gpui.controls.GPUIButton.REMOVE_HINT,this);
         mov.hintInstance = instance;
         this.hintArr[instance].mc = mov;
         mov.addEventListener(lol.gpui.controls.GPUIButton.SHOW_HINT,this);
         mov.addEventListener(lol.gpui.controls.GPUIButton.REMOVE_HINT,this);
      }
      this.hintArr[instance].folowMouse = folowMouse != undefined ? folowMouse : true;
   }
   function deleteHint(instance)
   {
      this.hintArr[instance].mc.removeEventListener(lol.gpui.controls.GPUIButton.SHOW_HINT,this);
      this.hintArr[instance].mc.removeEventListener(lol.gpui.controls.GPUIButton.REMOVE_HINT,this);
   }
   function killHint()
   {
      for(var _loc2_ in this.hintArr)
      {
         if(this.hintArr[_loc2_].mc)
         {
            this.hintArr[_loc2_].mc.removeEventListener(lol.gpui.controls.GPUIButton.SHOW_HINT,this);
            this.hintArr[_loc2_].mc.removeEventListener(lol.gpui.controls.GPUIButton.REMOVE_HINT,this);
            this.hintArr[_loc2_].mc.removeMovieClip();
            this.hintArr[_loc2_].mc = null;
         }
      }
   }
   function showAll()
   {
      var _loc3_;
      var _loc5_;
      var _loc4_;
      var _loc2_;
      if(this.F1)
      {
         for(var _loc6_ in this.hintArr)
         {
            if(this.hintArr[_loc6_].mc)
            {
               if(this.hintArr[_loc6_].check == undefined || this.hintArr[_loc6_].checkLink[this.hintArr[_loc6_].check])
               {
                  _loc3_ = this.hintArr[_loc6_].link;
                  _loc5_ = _loc3_._x;
                  _loc4_ = _loc3_._y;
                  _loc2_ = new Object();
                  _loc2_.x = _loc5_;
                  _loc2_.y = _loc4_;
                  _loc3_._parent.localToGlobal(_loc2_);
                  this.newHint(_loc6_,true,_loc2_.x - lol.gpui.HintManager.hintLayer._x,_loc2_.y - lol.gpui.HintManager.hintLayer._y);
               }
            }
         }
      }
      else
      {
         this.removeAll();
      }
   }
   function removeAll()
   {
      this.F1 = false;
      for(var _loc2_ in lol.gpui.HintManager.hintLayer)
      {
         lol.gpui.HintManager.hintLayer[_loc2_].showOut();
      }
   }
   function newHint(link, group, x, y)
   {
      lol.gpui.HintManager.hintLayer[this.prevLink].showOut();
      this.hintArr[link].show = true;
      var _loc7_ = this.hintArr[link].text;
      var _loc3_ = lol.core.SceneShifter.hotKeyManager.getHotKeyArr()[this.hintArr[link].hotKey].keyCode;
      var _loc4_ = "";
      var _loc2_;
      if(_loc3_)
      {
         _loc2_ = 0;
         while(_loc2_ < _loc3_.length)
         {
            if(_loc2_ != 0)
            {
               _loc4_ += "+";
            }
            _loc4_ += lol.utils.CharFromCode.getChar(_loc3_[_loc2_]);
            _loc2_ = _loc2_ + 1;
         }
         _loc7_ += " ( " + _loc4_ + " )";
      }
      var _loc5_ = new Object();
      _loc5_.str = _loc7_;
      _loc5_.x = x;
      _loc5_.y = y;
      _loc5_.mc = this.hintArr[link].mc;
      _loc5_.folowMouse = this.hintArr[link].folowMouse;
      if(!group)
      {
         if(lol.gpui.HintManager.hintLayer[this.prevLink].build)
         {
            _loc5_.pause = 0;
         }
         else
         {
            _loc5_.pause = lol.gpui.HintManager.TIME_PAUSE;
         }
      }
      else
      {
         _loc5_.pause = 0;
      }
      var _loc8_;
      if(!lol.gpui.HintManager.hintLayer[link])
      {
         _loc8_ = lol.gpui.HintManager.hintLayer.attachMovie("hintMC",link,lol.gpui.HintManager.hintLayer.getNextHighestDepth());
         _loc8_.param = _loc5_;
      }
      this.prevLink = link;
   }
   function removeHint(obj)
   {
      var _loc2_ = obj.target.hintInstance;
      lol.gpui.HintManager.hintLayer[_loc2_].showOut();
      this.hintArr[_loc2_].show = false;
   }
   function onKeyDown()
   {
      if(Key.getCode() == 49 && !this.keyD)
      {
         this.F1 = !this.F1;
         this.keyD = true;
      }
   }
   function onKeyUp()
   {
      if(Key.getCode() == 49)
      {
         this.keyD = false;
      }
   }
}
