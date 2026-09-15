class lol.gpui.PersGeneratorPan extends lol.gpui.GPUIObject
{
   var avatars;
   var bodies;
   var description_txt;
   var generatedPers;
   var lesson_btn;
   var manArray;
   var page0;
   var page1;
   var page2;
   var pages;
   var persGen;
   var readyChars;
   var selectAvatar_mc;
   var selectedPers;
   var start_fr;
   var vBar;
   var womanArray;
   var count = 0;
   var flag = false;
   var maleListNum = 1;
   var femaleListNum = 1;
   var male_arr = new Array();
   var female_arr = new Array();
   var avatarWidth = 76;
   var manNum = 0;
   var womanNum = 0;
   function PersGeneratorPan()
   {
      super();
      this.doLater(this,"init");
   }
   function init()
   {
      var _loc2_ = lol.core.Master.getInstance();
      this.persGen = _loc2_.persGen;
      this.persGen.addEventListener("failed",this);
   }
   function startCreate(av_arr, b_arr, readyArr, fr)
   {
      this.avatars = av_arr;
      this.bodies = b_arr;
      this.readyChars = readyArr;
      this.start_fr = fr;
      this._startCreate();
   }
   function _startCreate()
   {
      this.initPages();
      this.showPage(this.start_fr);
   }
   function initPages()
   {
      Key.addListener(this);
      this.pages = [this.page0,this.page1,this.page2];
      this.initPage0();
      this.initPage1();
   }
   function initPage0()
   {
      this.page0.create_btn.label = "Создать персонажа";
      this.page0.create_btn.addEventListener("click",this,this.nextPage);
      this.page0.select_btn.label = "Выбрать";
      this.page0.select_btn.onPress = mx.utils.Delegate.create(this,this.sendSelectPers);
      this.persInfo();
   }
   function persInfo()
   {
      var _loc3_ = this.page0.createEmptyMovieClip("cont",0);
      _loc3_._x = 50;
      _loc3_._y = 30;
      var _loc2_ = 0;
      while(_loc2_ < this.readyChars.length)
      {
         this.addPers(this.readyChars[_loc2_]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function addPers(persInfo)
   {
      var _loc3_ = this.page0.cont.getNextHighestDepth();
      var _loc2_ = this.page0.cont.attachMovie("avatar_cont","av" + _loc3_,_loc3_,{_x:_loc3_ * 100,_y:40});
      _loc2_.label = persInfo.name;
      _loc2_._label._y = 110;
      _loc2_.addEventListener("click",this,this.selectPers);
      var _loc6_ = lol.services.SSEmulator.getAvatarURL(persInfo.avatar.id,0);
      var _loc5_ = lol.display.DisplaySprite.create(_loc2_,"icon",0);
      _loc5_.display("avatar" + persInfo.avatar.id,_loc6_);
      _loc2_.data = persInfo;
   }
   function selectPers(obj)
   {
      this.selectedPers = obj.target.data;
      var _loc2_ = obj.target.data;
   }
   function sendSelectPers(obj)
   {
      if(this.selectedPers)
      {
         this.persGen.selectPers({persInfo:this.persInfo});
         this.page0.select_btn.removeEventListener("click",this);
      }
   }
   function initPage1()
   {
      this.lesson_btn._visible = false;
      lol.core.SceneShifter.enterWinFrame._visible = true;
      this.vBar = this.page1.vBar;
      this.description_txt = this.page1.description_txt;
      this.vBar._visible = false;
      this.vBar.setSize(this.description_txt._height - 10);
      this.vBar.target = this.description_txt;
      this.description_txt.onScroller = mx.utils.Delegate.create(this,this.scrollText);
      this.lesson_btn = this.page1.lesson_btn;
      this.lesson_btn.addEventListener("click",this,this.startLesson);
      this.lesson_btn.enabled = false;
      this.page1.next_btn.addEventListener("click",this,this.sendResult);
      this.page1.next_btn.enabled = false;
      this.page1.back_btn.label = "Назад";
      this.page1.back_btn.addEventListener("click",this,this.prevPage);
      this.createPers();
      this.page1.maleLeft_btn.onPress = mx.utils.Delegate.create(this,this.mLeft);
      this.page1.maleRight_btn.onPress = mx.utils.Delegate.create(this,this.mRight);
      this.page1.femaleLeft_btn.onPress = mx.utils.Delegate.create(this,this.fLeft);
      this.page1.femaleRight_btn.onPress = mx.utils.Delegate.create(this,this.fRight);
      this.moveTo("male",1);
      this.moveTo("female",1);
      this.moveTo("male",-1);
      this.moveTo("female",-1);
      this.moveTo("male",-1);
      this.moveTo("female",-1);
      this.checkBtn();
   }
   function scrollUp()
   {
      this.flag = true;
   }
   function scrollDown()
   {
      this.flag = true;
   }
   function stopScroll()
   {
      this.flag = false;
   }
   function scrollText()
   {
      var _loc2_;
      if(this.vBar.sliderButton.onMouseMove == undefined && !this.flag)
      {
         _loc2_ = (this.description_txt.scroll - 1) * 100 / this.description_txt.maxscroll;
         if(this.description_txt.maxscroll == this.description_txt.scroll)
         {
            _loc2_ = 100;
         }
         if(_loc2_ < 100)
         {
            this.vBar.__position = _loc2_;
         }
         else
         {
            this.vBar.__position = 100;
         }
      }
      this.chekTextSize();
   }
   function chekTextSize()
   {
      if(this.description_txt.textHeight > this.description_txt._height)
      {
         this.vBar._visible = true;
      }
      else
      {
         this.vBar._visible = false;
      }
   }
   function mLeft()
   {
      this.moveTo("male",-1);
   }
   function mRight()
   {
      this.moveTo("male",1);
   }
   function fLeft()
   {
      this.moveTo("female",-1);
   }
   function fRight()
   {
      this.moveTo("female",1);
   }
   function moveTo(sex, direct)
   {
      var _loc4_ = this[sex + "_arr"].length - 4;
      var _loc5_;
      if(direct == 1 && this[sex + "ListNum"] < _loc4_)
      {
         this[sex + "ListNum"] += direct;
         _loc5_ = Math.ceil((1.5 + this[sex + "ListNum"]) * this.avatarWidth) + 5;
         this.page1[sex + "Lent"].slideToCenter(_loc5_,103);
         this.checkBtn();
      }
      if(direct == -1 && this[sex + "ListNum"] > 1)
      {
         this[sex + "ListNum"] += direct;
         _loc5_ = Math.ceil((1.5 + this[sex + "ListNum"]) * this.avatarWidth) - 5;
         this.page1[sex + "Lent"].slideToCenter(_loc5_,103);
         this.checkBtn();
      }
   }
   function checkBtn()
   {
      this.page1.maleLeft_btn._visible = this.maleListNum != 1;
      this.page1.maleRight_btn._visible = this.maleListNum != this.male_arr.length - 4;
      this.page1.femaleLeft_btn._visible = this.femaleListNum != 1;
      this.page1.femaleRight_btn._visible = this.femaleListNum != this.female_arr.length - 4;
   }
   function onLoadSource(obj)
   {
      obj.target.removeEventListener("onLoadSource",this);
      var _loc2_ = this.page1.maleLent.content;
      var _loc3_ = this.page1.femaleLent.content;
   }
   function createPers()
   {
      this.generatedPers = new lol.core.player.PersInfo();
      this.male_arr = new Array();
      this.female_arr = new Array();
      var _loc11_ = this.page1.maleLent.fillContent();
      var _loc9_ = this.page1.femaleLent.fillContent();
      this.page1.maleLent.setSize(380,205);
      this.page1.femaleLent.setSize(380,205);
      this.manArray = new Array();
      this.womanArray = new Array();
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      var _loc5_;
      var _loc6_;
      while(_loc2_ < this.avatars.length)
      {
         if(this.avatars[_loc2_].sex < 128 || this.avatars[_loc2_].sex == "man")
         {
            _loc4_ = this.page1.maleLent.content.getNextHighestDepth();
            _loc3_ = this.page1.maleLent.content.attachMovie("avatarCont","av" + _loc4_,_loc4_);
            _loc3_._x = _loc4_ * this.avatarWidth;
            _loc3_.txt.text = _loc4_ + 1 >= 10 ? _loc4_ + 1 : "0" + (_loc4_ + 1);
            this.male_arr[_loc4_] = this.avatars[_loc2_];
         }
         else
         {
            _loc4_ = this.page1.femaleLent.content.getNextHighestDepth();
            _loc3_ = this.page1.femaleLent.content.attachMovie("avatarCont","av" + _loc4_,_loc4_);
            _loc3_._x = _loc4_ * this.avatarWidth;
            _loc3_.txt.text = _loc4_ + 1 >= 10 ? _loc4_ + 1 : "0" + (_loc4_ + 1);
            this.female_arr[_loc4_] = this.avatars[_loc2_];
         }
         if(this.avatars[_loc2_].id == "dummy1" || this.avatars[_loc2_].id == "dummy2")
         {
            _loc3_.onPress = function()
            {
            };
            _loc3_.useHandCursor = false;
         }
         else
         {
            if(this.avatars[_loc2_].sex < 128 || this.avatars[_loc2_].sex == "man")
            {
               this.manNum = this.manNum + 1;
               this.manArray.push(_loc3_);
            }
            else
            {
               this.womanNum = this.womanNum + 1;
               this.womanArray.push(_loc3_);
            }
            _loc3_.addEventListener("click",this,this.selectAvatar);
            _loc3_.avatar = this.avatars[_loc2_];
         }
         _loc5_ = lol.display.DisplaySprite.create(_loc3_.cont,"icon",0);
         _loc6_ = lol.services.SSEmulator.getAvatarURL(this.avatars[_loc2_].id,0);
         _loc5_.display("avatar" + this.avatars[_loc2_].id,_loc6_);
         _loc5_.addEventListener("onLoadSource",this);
         _loc2_ = _loc2_ + 1;
      }
      var _loc8_ = Math.round(Math.random());
      var _loc7_;
      if(_loc8_ == 0)
      {
         _loc7_ = Math.round(Math.random() * (this.manNum - 1));
         this.manArray[_loc7_].toggled = true;
         this.selectAvatar({target:this.manArray[_loc7_]});
      }
      else
      {
         _loc7_ = Math.round(Math.random() * (this.womanNum - 1));
         this.womanArray[_loc7_].toggled = true;
         this.selectAvatar({target:this.womanArray[_loc7_]});
      }
      this.page1.nickname_txt.text = "Введите ник";
      this.page1.nickname_txt.onChanged = mx.utils.Delegate.create(this,this.inputNick);
      this.page1.nickname_txt.onSetFocus = mx.utils.Delegate.create(this,this.nickFocus);
      this.page1.nickname_txt.onKillFocus = mx.utils.Delegate.create(this,this.nickFocus);
      this.page1.smsCode_txt._visible = false;
      this.page1.apply_btn.label = "Ok";
      this.page1.apply_btn._visible = false;
      this.page1.apply_btn.onPress = mx.utils.Delegate.create(this,this.sendSmsCode);
   }
   function selectAvatar(obj)
   {
      var _loc4_ = new TextFormat();
      _loc4_.color = 10262413;
      var _loc3_ = new TextFormat();
      _loc3_.color = 3881268;
      if(this.selectAvatar_mc != obj.target)
      {
         this.selectAvatar_mc.txt.setTextFormat(_loc4_);
         this.selectAvatar_mc.toggled = false;
         this.selectAvatar_mc = obj.target;
         this.selectAvatar_mc.toggled = true;
         this.selectAvatar_mc.txt.setTextFormat(_loc3_);
      }
      var _loc6_;
      var _loc5_;
      var _loc7_;
      var _loc8_;
      if(this.selectAvatar_mc.toggled == true)
      {
         _loc6_ = obj.target.avatar.description;
         this.description_txt.htmlText = _loc6_;
         this.vBar.setSize(this.description_txt._height - 10);
         _loc5_ = lol.display.DisplaySprite.create(this.page1.bigAvatar,"bav",0);
         _loc7_ = obj.target.avatar.id;
         _loc8_ = lol.services.SSEmulator.getAvatarURL(obj.target.avatar.id,1);
         _loc5_.display("big_avatar" + _loc7_,_loc8_);
         this.checkAvatarHight(_loc5_);
         this.checkAvatar(obj);
      }
      else
      {
         this.selectAvatar_mc.toggled = true;
      }
      this.checkPage1();
   }
   function checkAvatarHight(ba)
   {
      var _loc2_ = this.page1.bigAvatar._height;
      if(_loc2_ != 0 && _loc2_ != undefined)
      {
         this.page1.bigAvatar._y = 448 - _loc2_;
      }
      else
      {
         ba.addEventListener("onLoadSource",this,this.checkOnLoadSource);
      }
   }
   function checkOnLoadSource(obj)
   {
      obj.removeEventListener("onLoadSource",this,this.checkAvatarHight);
      var _loc2_ = this.page1.bigAvatar._height;
      this.page1.bigAvatar._y = 448 - _loc2_;
   }
   function checkAvatar(obj)
   {
      if(obj.target.avatar.buy == "free")
      {
         this.generatedPers.avatar = obj.target.avatar;
         this.generatedPers.sex = obj.target.avatar.sex;
         obj.target.toggled = true;
         this.page1.smsCode_txt._visible = false;
         this.page1.apply_btn._visible = false;
      }
      else
      {
         this.generatedPers.avatar = undefined;
         this.page1.smsCode_txt._visible = true;
         this.page1.apply_btn._visible = true;
      }
   }
   function sendSmsCode()
   {
   }
   function accessCode()
   {
   }
   function inputNick()
   {
      this.generatedPers.name = this.page1.nickname_txt.text;
      this.checkPage1();
   }
   function nickFocus()
   {
      var _loc2_ = this.page1.nickname_txt.text;
      if(_loc2_.length <= 0)
      {
         this.page1.nickname_txt.text = "Введите ник";
      }
      if(_loc2_ == "Введите ник")
      {
         this.page1.nickname_txt.text = "";
      }
   }
   function checkPage1()
   {
      if(this.generatedPers.avatar && this.generatedPers.name.length > 1)
      {
         this.page1.next_btn.enabled = true;
         this.lesson_btn.enabled = true;
      }
      else
      {
         this.page1.next_btn.enabled = false;
         this.lesson_btn.enabled = false;
      }
   }
   function checkPage2()
   {
   }
   function sendResult()
   {
      lol.core.SceneShifter.firstGame = true;
      this.persGen.generatePers({persInfo:this.generatedPers});
   }
   function failed()
   {
      Key.addListener(this);
   }
   function startLesson()
   {
      lol.core.SceneShifter.firstGame = true;
      this.persGen.playHelp_bool = true;
      this.persGen.generatePers({persInfo:this.generatedPers});
   }
   function nextPage()
   {
      this.count = this.count + 1;
      if(this.count >= this.pages.length)
      {
         this.count = this.pages.length - 1;
      }
      this.showPage();
   }
   function prevPage()
   {
      this.count = this.count - 1;
      if(this.count <= 0)
      {
         this.count = 0;
      }
      this.showPage();
   }
   function showPage(c)
   {
      this.count = c == undefined ? this.count : c;
      var _loc2_ = 0;
      while(_loc2_ < this.pages.length)
      {
         this.pages[_loc2_]._visible = false;
         _loc2_ = _loc2_ + 1;
      }
      this.pages[this.count]._visible = true;
   }
   function gotoEnd()
   {
      this.count = this.pages.length - 1;
      this.showPage();
   }
   function gotoBegin()
   {
      this.count = 0;
      this.showPage();
   }
   function gotoFirst()
   {
      this.count = 1;
      this.showPage();
   }
   function onKeyDown()
   {
      if(Key.isDown(13))
      {
         if(lol.core.SceneShifter._sl.activeWindow == "persGenPanel" && this.page1.next_btn.enabled)
         {
            this.sendResult();
            Key.removeListener(this);
         }
      }
      if(!Key.isDown(16))
      {
      }
   }
}
