class lol.gpui.HelpDropList extends lol.gpui.GPUIObject
{
   var _xmouse;
   var _y;
   var _ymouse;
   var cont_mc;
   var faq_btn;
   var forum_btn;
   var getURL;
   var lessonsArr;
   var lessons_btn;
   var onEnterFrame;
   var support_btn;
   var _open = false;
   function HelpDropList()
   {
      super();
      this.doLater("init");
      this.loadXML();
      this.cont_mc._visible = false;
   }
   function init()
   {
      this.support_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.support);
      this.faq_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.faq);
      this.lessons_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.lessons);
      this.forum_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.forum);
   }
   function kill()
   {
      this.support_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.support);
      this.faq_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.faq);
      this.lessons_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.lessons);
      this.forum_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.forum);
      var _loc2_ = 0;
      while(_loc2_ < this.lessonsArr.length)
      {
         this.lessonsArr[_loc2_].mc.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectLesson);
         this.lessonsArr[_loc2_].mc.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.selectLesson);
         this.lessonsArr[_loc2_].mc.removeEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this,this.selectLesson);
         this.lessonsArr[_loc2_].mc.removeEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.selectLesson);
         _loc2_ = _loc2_ + 1;
      }
   }
   function loadXML()
   {
      var _loc2_ = lol.services.Help.getInstance();
      _loc2_.addEventListener("onLoad",this,this.onXML);
      _loc2_.start();
   }
   function onXML(obj)
   {
      obj.target.removeEventListener("onLoad",this,this.onXML);
      this.lessonsArr = lol.services.Help.getInstance().lessonsArr;
      this.buildLessonsList();
   }
   function buildLessonsList()
   {
      var _loc18_ = this.cont_mc.createEmptyMovieClip("lessonsCont",this.cont_mc.getNextHighestDepth());
      var _loc25_ = 0;
      var _loc3_ = 0;
      var _loc5_;
      var _loc17_;
      while(_loc3_ < this.lessonsArr.length)
      {
         _loc5_ = _loc18_.attachMovie("lessonsItem_btn","lessonsItem_btn" + _loc3_,_loc3_);
         _loc5_.id = _loc3_;
         _loc5_._y = _loc3_ * 17;
         _loc5_.title_txt.autoSize = true;
         _loc5_.title_txt.text = _loc3_ + 1 + ". " + this.lessonsArr[_loc3_].title;
         _loc17_ = new TextFormat();
         _loc17_.bold = true;
         _loc5_.title_txt.setTextFormat(_loc17_);
         if(this.lessonsArr[_loc3_].active == "true")
         {
            this.doLater("initListeners",[_loc5_]);
            this.lessonsArr[_loc3_].mc = _loc5_;
         }
         else
         {
            _loc5_._enabled = false;
            _loc5_._alpha = 60;
         }
         _loc3_ = _loc3_ + 1;
      }
      var _loc20_ = this.cont_mc.back_mc.leftTop_mc;
      var _loc14_ = this.cont_mc.back_mc.top_mc;
      var _loc19_ = this.cont_mc.back_mc.rightTop_mc;
      var _loc13_ = this.cont_mc.back_mc.left_mc;
      var _loc15_ = this.cont_mc.back_mc.right_mc;
      var _loc16_ = this.cont_mc.back_mc.bottom_mc;
      var _loc21_ = this.cont_mc.back_mc.leftBottom_mc;
      var _loc22_ = this.cont_mc.back_mc.rightBottom_mc;
      var _loc4_ = this.cont_mc.back_mc.center_mc;
      this.cont_mc.back_mc.onPress = function()
      {
      };
      var _loc24_ = _loc18_._width;
      var _loc23_ = _loc18_._height;
      var _loc12_ = Math.ceil(_loc24_ / _loc4_._width);
      var _loc7_ = Math.ceil(_loc23_ / _loc4_._height);
      _loc3_ = 0;
      var _loc2_;
      var _loc9_;
      var _loc11_;
      var _loc6_;
      var _loc8_;
      var _loc10_;
      while(_loc3_ <= _loc7_)
      {
         _loc2_ = 0;
         while(_loc2_ <= _loc12_)
         {
            _loc9_ = _loc4_.duplicateMovieClip("c_mc" + _loc3_ + "_" + _loc2_,this.cont_mc.back_mc.getNextHighestDepth());
            _loc9_._x = _loc2_ * _loc4_._width;
            _loc9_._y = _loc3_ * _loc4_._height;
            if(_loc2_ == 0 && _loc3_ != _loc7_)
            {
               _loc11_ = _loc13_.duplicateMovieClip("l_mc" + _loc3_ + "_" + _loc2_,this.cont_mc.back_mc.getNextHighestDepth());
               _loc11_._x = - _loc13_._width;
               _loc11_._y = _loc3_ * _loc13_._height;
            }
            if(_loc2_ == _loc12_ && _loc3_ != _loc7_)
            {
               _loc6_ = _loc15_.duplicateMovieClip("r_mc" + _loc3_ + "_" + _loc2_,this.cont_mc.back_mc.getNextHighestDepth());
               _loc6_._x = (_loc12_ + 1) * _loc4_._width + _loc6_._width;
               _loc6_._y = _loc3_ * _loc15_._height;
            }
            if(_loc3_ == 0)
            {
               _loc8_ = _loc14_.duplicateMovieClip("t_mc" + _loc3_ + "_" + _loc2_,this.cont_mc.back_mc.getNextHighestDepth());
               _loc8_._x = _loc2_ * _loc14_._width;
               _loc8_._y = - _loc14_._height;
            }
            if(_loc3_ == _loc7_)
            {
               _loc10_ = _loc16_.duplicateMovieClip("b_mc" + _loc3_ + "_" + _loc2_,this.cont_mc.back_mc.getNextHighestDepth());
               _loc10_._x = _loc2_ * _loc16_._width;
               _loc10_._y = _loc7_ * _loc4_._height;
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc3_ = _loc3_ + 1;
      }
      _loc20_._x = - _loc20_._width;
      _loc20_._y = - _loc20_._height;
      _loc19_._x = (_loc12_ + 1) * _loc4_._width + _loc19_._width;
      _loc19_._y = - _loc19_._height;
      _loc21_._x = - _loc21_._width;
      _loc21_._y = _loc7_ * _loc4_._height;
      _loc22_._x = (_loc12_ + 1) * _loc4_._width + _loc22_._width;
      _loc22_._y = _loc7_ * _loc4_._height;
      _loc4_.removeMovieClip();
      _loc13_.removeMovieClip();
      _loc15_.removeMovieClip();
      _loc14_.removeMovieClip();
      _loc16_.removeMovieClip();
      _loc18_.swapDepths(this.cont_mc.getNextHighestDepth());
   }
   function initListeners(btn)
   {
      btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectLesson);
      btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this,this.rollOut);
      btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.rollOver);
      btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.rollOver);
   }
   function rollOver(obj)
   {
      obj.target.title_txt.textColor = 13421772;
   }
   function rollOut(obj)
   {
      obj.target.title_txt.textColor = 10066329;
   }
   function onMouseDown()
   {
      var _loc3_ = this._xmouse;
      var _loc2_ = this._ymouse;
      var _loc4_ = this.cont_mc._x;
      var _loc6_ = _loc4_ + this.cont_mc._width;
      var _loc5_ = this.cont_mc._y;
      var _loc7_ = _loc5_ + this.cont_mc._height;
      if(_loc3_ < _loc4_ || _loc3_ > _loc6_ || _loc2_ < _loc5_ || _loc2_ > _loc7_)
      {
         if(_loc3_ < 0 || _loc3_ > 125 || _loc2_ < -22 || _loc2_ > 110)
         {
            this.close();
         }
         else
         {
            this.cont_mc._visible = false;
         }
      }
      else if(!this.cont_mc._visible)
      {
         this.close();
      }
   }
   function selectLesson(obj)
   {
      this.openClose();
      var _loc2_ = lol.core.SceneShifter.openNewWindow("helpVideoLessons","globalCenter");
      _loc2_.content.lessonsArr = this.lessonsArr;
      _loc2_.content.curLesson = obj.target.id;
   }
   function support()
   {
      this.openClose();
      this.getURL("http://lava-online.ru/exe/node/view/id/121","_blank");
   }
   function faq()
   {
      this.openClose();
      this.getURL("http://www.lava-online.ru/faq.html","_blank");
   }
   function lessons(obj)
   {
      if(obj.target.toggled)
      {
         this.cont_mc._visible = true;
      }
   }
   function forum()
   {
      this.openClose();
      this.getURL("http://www.lava-online.ru/forum/forum_9","_blank");
   }
   function openClose()
   {
      if(!this._open)
      {
         this.open();
      }
      else
      {
         this.close();
      }
   }
   function open()
   {
      delete this.onEnterFrame;
      this.onEnterFrame = function()
      {
         var _loc2_ = 45 - this._y;
         this._y += _loc2_ / 1.5;
         if(_loc2_ <= 2)
         {
            delete this.onEnterFrame;
         }
      };
      this._open = true;
   }
   function close()
   {
      this.cont_mc._visible = false;
      this.lessons_btn.toggled = false;
      delete this.onEnterFrame;
      this.onEnterFrame = function()
      {
         var _loc2_ = this._y + 80;
         this._y -= _loc2_ / 1.5;
         if(_loc2_ <= 2)
         {
            delete this.onEnterFrame;
         }
      };
      this._open = false;
   }
}
