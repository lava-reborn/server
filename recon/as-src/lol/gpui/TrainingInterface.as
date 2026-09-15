class lol.gpui.TrainingInterface extends lol.gpui.GPUIObject
{
   var HTTP;
   var attributes;
   var buy_btn;
   var close_btn;
   var cur_spec;
   var currentSlideListNum;
   var currentSpec;
   var currentSpecId;
   var dispatchEvent;
   var infoPan;
   var listArr;
   var max_spec;
   var price_mc;
   var slideList;
   var specArr;
   var specInfo_txt;
   var specItemArr;
   var take_btn;
   var throw_btn;
   var training;
   var xmlArr;
   var xmlInfoLoaded;
   static var MIN_SKILL = 0;
   function TrainingInterface()
   {
      super();
      this.initArray();
      this.doLater("init");
      this.loadDescription();
      this.attributes = lol.core.Master.getInstance().gamer.attributes;
      this.attributes.addEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.rpUpdate);
      this.throw_btn._visible = false;
      this.take_btn._visible = false;
      this.price_mc._visible = false;
      this.buy_btn._visible = false;
      lol.core.SceneShifter.locationScreen.centerChar();
   }
   function init()
   {
      this.training = lol.core.Master.getInstance().gamer.training;
      lol.core.Master.getInstance().gamer.requestAttributes();
      this.training.addEventListener("close",this,this.trainingClose);
      this.infoPan.fillContent();
      this.infoPan.setSize(393,100);
      this.throw_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.forgetSpec);
      this.take_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.learnSpec);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      lol.core.SceneShifter.hotKeyManager.addFilter("training");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER0,this,this.selectFuncKey1);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER1,this,this.selectFuncKey2);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER2,this,this.selectFuncKey3);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER3,this,this.selectFuncKey4);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FILTER4,this,this.selectFuncKey5);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.rpUpdate();
   }
   function trainingClose()
   {
      this.close();
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.training.removeEventListener("close",this,this.trainingClose);
      this.training.close();
      this.throw_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.forgetSpec);
      this.take_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.learnSpec);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.attributes.removeEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.rpUpdate);
      lol.core.SceneShifter.hotKeyManager.removeFilter("training");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER0,this,this.selectFuncKey1);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER1,this,this.selectFuncKey2);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER2,this,this.selectFuncKey3);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER3,this,this.selectFuncKey4);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FILTER4,this,this.selectFuncKey5);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function learnSpec()
   {
      if(this.currentSpecId != undefined)
      {
         this.training.learn(this.currentSpecId);
      }
   }
   function forgetSpec()
   {
      var _loc3_ = lol.core.SceneShifter.openNewWindow("query");
      var _loc2_ = _loc3_.content;
      _loc2_.label = "Сбросить специализацию?";
      _loc2_.addEventListener("click",this,this.forgetSpecAck);
   }
   function forgetSpecAck(obj)
   {
      obj.target.removeEventListener("click",this,this.forgetSpecAck);
      lol.core.SceneShifter.closeWindow("query");
      var _loc2_ = obj.success;
      if(_loc2_)
      {
         if(this.currentSpecId || this.currentSpecId == 0)
         {
            this.training.forget(this.currentSpecId);
         }
      }
   }
   function selectFuncKey1()
   {
      this.slideList.open(0);
   }
   function selectFuncKey2()
   {
      this.slideList.open(1);
   }
   function selectFuncKey3()
   {
      this.slideList.open(2);
   }
   function selectFuncKey4()
   {
      this.slideList.open(3);
   }
   function selectFuncKey5()
   {
      this.slideList.open(4);
   }
   function rpUpdate(obj)
   {
      this.currentSlideListNum = this.slideList.currentNum;
      this.currentSpec = null;
      this.currentSpecId = null;
      this.throw_btn._visible = false;
      this.buy_btn._visible = false;
      this.take_btn._visible = false;
      this.slideList.setSize(410,178);
      this.initArray();
      this.slideList.erase();
      this.listArr = this.slideList.build(this.specArr);
      this.attachSpec();
      this.max_spec = lol.core.Master.getInstance().gamer.attributes.max_specs;
      this.cur_spec = lol.core.Master.getInstance().gamer.attributes.getSpecNumber();
      this.specInfo_txt.text = "Изучается: " + this.cur_spec + " спец., доступно для изучения: " + this.max_spec + " спец.";
      this.specInfo_txt._visible = false;
      this.doLater("slidelistOpen");
   }
   function slidelistOpen()
   {
      this.slideList.open(this.currentSlideListNum);
   }
   function initArray()
   {
      var _loc3_ = this.attributes.skillArray;
      var _loc10_ = this.attributes.specArray;
      this.specArr = new Array();
      var _loc2_ = 0;
      while(_loc2_ < 4)
      {
         this.specArr[_loc2_] = {title:_loc3_[_loc2_].title,linkTitle:"slide" + _loc2_ + "_btn",linkContent:"contextListPan",skillNum:_loc3_[_loc2_].levelString,currentSkill:_loc3_[_loc2_].currentValue,spec:_loc3_[_loc2_].specArr};
         _loc2_ = _loc2_ + 1;
      }
   }
   function loadDescription()
   {
      this.HTTP = new lol.server.HTTPRequest();
      this.HTTP.addEventListener("onXML",this);
      var _loc2_ = lol.services.SSEmulator.getSpecXmlURL();
      this.HTTP.Send("",_loc2_);
   }
   function onXML(obj)
   {
      this.xmlInfoLoaded = true;
      this.parse(obj.data);
      this.HTTP.removeEventListener("onXML",this);
      this.HTTP.kill();
      this.HTTP = null;
   }
   function parse(doc)
   {
      this.xmlArr = new Array();
      var _loc5_ = doc.firstChild.childNodes;
      var _loc3_;
      var _loc4_;
      var _loc2_;
      for(var _loc7_ in _loc5_)
      {
         _loc3_ = new Object();
         _loc3_ = _loc5_[_loc7_].attributes;
         _loc4_ = new Array();
         _loc2_ = _loc5_[_loc7_].childNodes;
         for(var _loc6_ in _loc2_)
         {
            _loc4_.push(_loc2_[_loc6_].childNodes[0]);
         }
         _loc3_.arr = _loc4_;
         this.xmlArr["s" + _loc5_[_loc7_].attributes.id] = _loc3_;
      }
   }
   function attachSpec()
   {
      var _loc9_ = 0;
      var _loc6_ = 0;
      var _loc5_;
      var _loc4_;
      var _loc2_;
      var _loc3_;
      while(_loc6_ < this.listArr.length)
      {
         _loc5_ = this.listArr[_loc6_].listBtn.cont;
         _loc4_ = this.specArr[_loc6_].spec;
         _loc5_.setSize(400,177);
         _loc5_.listItemLink = "slideItem";
         _loc5_.lineSpace = -6;
         _loc2_ = 0;
         while(_loc2_ < _loc4_.length)
         {
            _loc3_ = _loc5_.addItem({label:_loc4_[_loc2_].title,data:_loc4_[_loc2_]});
            _loc3_.addEventListener("click",this,this.selectSpec);
            this.specItemArr.push(_loc3_);
            _loc9_ = _loc9_ + 1;
            _loc2_ = _loc2_ + 1;
         }
         _loc6_ = _loc6_ + 1;
      }
   }
   function selectSpec(obj)
   {
      var _loc3_;
      if(this.currentSpec != obj.target)
      {
         this.currentSpec.toggled = false;
         this.currentSpec = obj.target;
         this.currentSpecId = obj.target.data.id;
         _loc3_ = this.xmlArr["s" + obj.target.data.id];
      }
      else
      {
         this.currentSpec = null;
         this.currentSpecId = null;
         _loc3_ = "none";
      }
      this.showDesc(_loc3_,obj.target.data,obj.target.data.id);
   }
   function showDesc(xmlObj, btnObj, id)
   {
      this.infoPan.content.removeMovieClip();
      this.infoPan.fillContent();
      var _loc6_ = this.infoPan.content.attachMovie("skillInfo_title","skillInfo_title",this.infoPan.content.getNextHighestDepth());
      _loc6_.txt.autoSize = true;
      _loc6_.txt.wordWrap = true;
      var _loc4_;
      var _loc8_;
      var _loc10_;
      var _loc9_;
      var _loc5_;
      var _loc2_;
      var _loc11_;
      if(xmlObj != "none")
      {
         if(xmlObj)
         {
            _loc6_.txt.text = xmlObj.title;
         }
         else
         {
            _loc6_.txt.text = "У этой специализации нет описания или оно еще не загрузилось.";
         }
         _loc4_ = this.infoPan.content.attachMovie("skillInfo_label","skillInfo_label",this.infoPan.content.getNextHighestDepth());
         _loc4_.txt.autoSize = true;
         _loc4_.txt.wordWrap = false;
         _loc4_._y = _loc6_._y + _loc6_._height;
         _loc8_ = xmlObj.minSkill;
         _loc10_ = this.attributes.skillArray[this.slideList.currentNum].level;
         _loc9_ = this.specArr[this.slideList.currentNum].title;
         trace("minSkill = " + _loc8_ + ", skillNum = " + _loc10_ + ", title = " + _loc9_);
         if(Number(_loc8_) > _loc10_)
         {
            _loc4_.txt.htmlText = "<font color=\'#970d02\'>Требует навык \"" + _loc9_ + "\" не ниже " + _loc8_ + "</font>";
            _loc4_.label.gotoAndStop(2);
            if(this.throw_btn._visible)
            {
               this.throw_btn._visible = false;
            }
            if(this.take_btn._visible)
            {
               this.take_btn._visible = false;
            }
         }
         else
         {
            _loc4_.txt.htmlText = "<font color=\'#718d1e\'>Требует навык \"" + _loc9_ + "\" не ниже " + _loc8_ + "</font>";
            _loc4_.label.gotoAndStop(1);
            if(this.throw_btn._visible)
            {
               this.throw_btn._visible = false;
            }
            if(!this.take_btn._visible)
            {
               this.take_btn._visible = true;
            }
         }
         _loc4_.label._x = _loc4_.txt.textWidth + 5;
         if(!this.price_mc._visible)
         {
            this.price_mc._visible = true;
         }
         if(btnObj.level >= 0)
         {
            _loc4_.txt.htmlText += "<font color=\'#718d1e\'>Изучено на \"" + btnObj.level + "\"</font>";
            if(!this.throw_btn._visible)
            {
               this.throw_btn._visible = true;
            }
            if(this.price_mc._visible)
            {
               this.price_mc._visible = false;
            }
            if(this.take_btn._visible)
            {
               this.take_btn._visible = false;
            }
         }
         _loc5_ = _loc4_._y + _loc4_._height;
         for(var _loc7_ in xmlObj.arr)
         {
            _loc2_ = this.infoPan.content.attachMovie("skillInfo_item","skillInfo_item",this.infoPan.content.getNextHighestDepth());
            _loc2_.txt.autoSize = true;
            _loc2_.txt.wordWrap = true;
            _loc2_._y = _loc5_;
            _loc2_.txt.htmlText = xmlObj.arr[_loc7_];
            _loc5_ = _loc2_._y + _loc2_._height;
         }
         _loc11_ = lol.core.Master.getInstance().gamer.training.getCost();
         if(_loc11_.type == "afro")
         {
            this.price_mc.gotoAndStop(1);
         }
         else
         {
            this.price_mc.gotoAndStop(2);
         }
         this.price_mc.num.text = _loc11_.cost;
      }
      else
      {
         if(this.throw_btn._visible)
         {
            this.throw_btn._visible = false;
         }
         if(this.take_btn._visible)
         {
            this.take_btn._visible = false;
         }
         if(this.price_mc._visible)
         {
            this.price_mc._visible = false;
         }
      }
   }
}
